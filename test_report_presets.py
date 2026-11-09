import contextlib
import copy
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
import pandas as pd

from report_system.core.engine import DataProcessor, REPORT_TYPES, read_source_excel, save_workbook_from_template
from report_system.data.config_store import ConfigStore
from report_system.data.report_presets import ensure_builtin_presets, instantiate_preset
from report_system.data.template_library import TemplateLibrary
from report_system.ui.app import ReportGeneratorApp


class ReportPresetTests(unittest.TestCase):
    def test_saved_type_is_shared_across_products_and_owns_its_workbook(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "products" / "产品甲"
            second = root / "products" / "产品乙"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            template = first / "专用模板.xlsx"
            workbook = openpyxl.Workbook()
            workbook.active.title = "检验"
            workbook.save(template)
            workbook.close()
            app = ReportGeneratorApp.__new__(ReportGeneratorApp)
            app.root = MagicMock()
            app.config_file = str(first / "report_generator_config.json")
            app.template_library = TemplateLibrary(root)
            app.active_rule = "甲的首件表"
            app.active_template_profile = "专用"
            app.rules = {app.active_rule: {"base_type": "首件检验报表", "source_drawings": ["甲工序"],
                                          "column_mapping": {"检验项目": 2}}}
            app.template_profiles = {"专用": {"path": str(template), "sheet_config": {
                app.active_rule: {"sheet_name": "检验", "header": 4, "footer": 15}}}}
            app._store_rule_form = app._store_profile = MagicMock()
            app.status = MagicMock()
            with patch("report_system.ui.app.simpledialog.askstring", return_value="跨产品首件模板"):
                app.save_report_preset()
            # A different product opens a separate library instance in the same workspace.
            other_library = TemplateLibrary(second.parent.parent)
            saved = other_library.list_items()[0]
            self.assertEqual(saved["kind"], "report_type")
            self.assertEqual(saved["name"], "跨产品首件模板")
            template.unlink()
            preset = instantiate_preset(saved["config"], "甲的首件表", "乙的首件表", ["乙工序"])
            self.assertTrue(Path(preset["path"]).is_file())
            self.assertEqual(preset["rule"]["source_drawings"], ["乙工序"])
            other_library.update_metadata(saved["id"], {"name": "共享首件"})
            self.assertEqual(app.template_library.list_items()[0]["name"], "共享首件")
            other_library.delete(saved["id"])
            self.assertEqual(app.template_library.list_items(), [])
            self.assertTrue(Path(preset["path"]).is_file())

    def test_six_builtin_types_export_without_manual_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = TemplateLibrary(temporary)
            ensure_builtin_presets(library)
            ensure_builtin_presets(library)
            items = library.list_items()
            self.assertEqual(len(items), 6)
            fixture = Path(__file__).parent / "测试案例_四套" / "案例01-单工序基础"
            defaults = ConfigStore(fixture / "可导入模板配置.json").load()
            source = read_source_excel(fixture / "bubble_export.xlsx")
            drawings = list(source["图纸"].unique())
            processor = DataProcessor(source, pd.DataFrame(defaults["freq"]), defaults["item_trans"],
                                      defaults["tool_ship"], defaults["tool_proc"])
            for item in items:
                report = item["builtin_report_type"]
                with self.subTest(report=report):
                    preset = instantiate_preset(item["config"], report, "新报表", drawings)
                    processor.validate_drawings(preset["rule"])
                    frame = processor.build(report, preset["rule"])
                    self.assertGreater(len(frame), 0)
                    settings = preset["settings"]
                    output = Path(temporary) / "output.xlsx"
                    with contextlib.redirect_stdout(io.StringIO()):
                        save_workbook_from_template(preset["path"], str(output), {"新报表": frame},
                            {"新报表": (settings["sheet_name"], settings["header"], settings["footer"])},
                            {"新报表": preset["rule"]["column_mapping"]}, {}, {})
                    workbook = openpyxl.load_workbook(output, read_only=True)
                    try:
                        self.assertEqual(workbook[report].cell(7, 1).value, drawings[0])
                    finally:
                        workbook.close()

    def test_custom_type_resets_scope_and_revision_but_keeps_mapping(self):
        config = {"rules": {"旧报表": {"source_drawings": ["旧工序"], "report_version": "B",
                    "column_mapping": {"检验项目": 3}, "fixed_columns": {"9": "固定内容"}}},
                  "templates": {"path": "template.xlsx"},
                  "sheet_config": {"旧报表": {"sheet_name": "检验", "header": 5, "footer": 20}}}
        original = copy.deepcopy(config)
        preset = instantiate_preset(config, "旧报表", "新报表", ["新工序"])
        self.assertEqual(config, original)
        self.assertEqual(preset["rule"]["source_drawings"], ["新工序"])
        self.assertEqual(preset["rule"]["report_version"], "")
        self.assertEqual(preset["rule"]["fixed_columns"], {"9": "固定内容"})
        self.assertEqual(preset["settings"]["header"], 5)

    def test_install_preserves_other_reports_and_templates(self):
        with tempfile.TemporaryDirectory() as temporary:
            template = Path(temporary) / "template.xlsx"
            template.touch()
            app = ReportGeneratorApp.__new__(ReportGeneratorApp)
            app.rules = {"原报表": {"base_type": REPORT_TYPES[0]}}
            app.template_profiles = {"原模板": {"path": "original.xlsx", "sheet_config": {
                "原报表": {"sheet_name": "原表", "header": 8, "footer": 16}}}}
            for name in ("template_path", "profile_selector", "profile_var", "rule_selector",
                         "template_selector", "rule_report", "template_report", "status",
                         "_load_rule_form", "_load_template_form"):
                setattr(app, name, MagicMock())
            app._install_report_preset({"name": "新报表", "path": str(template), "rule": {"source_drawings": ["新工序"]},
                                       "settings": {"sheet_name": "新表", "header": 6, "footer": 14}})
            self.assertEqual(app.template_profiles["原模板"]["path"], "original.xlsx")
            self.assertEqual(app.template_profiles["原模板"]["sheet_config"]["原报表"]["header"], 8)
            self.assertEqual(app.sheet_config["新报表"]["header"], 6)
            self.assertEqual(app.sheet_config["原报表"]["header"], 0)
            self.assertEqual(app.active_rule, "新报表")
