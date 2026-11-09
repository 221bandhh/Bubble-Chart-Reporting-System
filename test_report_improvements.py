import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from contextlib import contextmanager
from test_baobiaosys import FakeWorksheet
from report_system.core.engine import save_workbook_from_template

import openpyxl
import pandas as pd
from report_system.core.engine import DataProcessor, DEFAULT_RULES
from report_system.data.config_store import ConfigStore
from report_system.ui.app import ReportGeneratorApp
from ui.bubble_app import BubbleApp
from core.bubble_engine import BubbleEngine
from data.product_repository import ProductRepository
from report_system.data.template_library import TemplateLibrary


class ReportImprovementTests(unittest.TestCase):
    def test_startup_skips_missing_product_without_deleting_index(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = ProductRepository(folder)
            missing = repository.create("A missing")
            valid = repository.create("B valid")
            (repository.product_dir(missing) / "product.json").unlink()
            app = BubbleApp.__new__(BubbleApp)
            app.repository = repository
            app.product_list = Mock()
            app._load_product = Mock()
            with patch("ui.bubble_app.messagebox.showwarning") as warning:
                app._refresh_products()
            warning.assert_called_once()
            app._load_product.assert_called_once_with(valid["id"])
            self.assertEqual(len(repository.list_products()), 2)

    def test_products_are_sorted_by_name(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = ProductRepository(folder)
            repository.create("Z product")
            repository.create("A product")
            self.assertEqual([p["name"] for p in repository.list_products()],
                             ["A product", "Z product"])

    def test_copy_previous_preserves_position_and_can_be_undone(self):
        app = BubbleApp.__new__(BubbleApp)
        app.drawing = {"id": "drawing"}
        engine = BubbleEngine([
            {"seq": 1, "x": 10, "y": 20, "req": "10", "internal": "9.9"},
            {"seq": 2, "x": 100, "y": 200, "req": "old"},
        ])
        app.engines = {"drawing": engine}
        app.tree = Mock()
        app.tree.selection.return_value = ("2",)
        app._changed = Mock()
        app.copy_previous_row()
        row = engine.get(2)
        self.assertEqual((row["seq"], row["x"], row["y"]), (2, 100, 200))
        self.assertEqual((row["req"], row["internal"]), ("10", "9.9"))
        self.assertTrue(engine.undo())
        self.assertEqual(engine.get(2)["req"], "old")

    def test_double_click_sequence_opens_editor(self):
        app = BubbleApp.__new__(BubbleApp)
        app.tree = Mock()
        app.tree.identify.return_value = "cell"
        app.tree.identify_row.return_value = "2"
        app.tree.identify_column.return_value = "#1"
        app._open_cell_editor = Mock()
        app._edit_cell(Mock(x=10, y=10))
        app._open_cell_editor.assert_called_once_with("2", "#1")

    def test_each_process_reads_only_selected_drawing(self):
        processor = DataProcessor(pd.DataFrame([
            {"图纸": "车削", "检验项目": "外径", "序号": "1"},
            {"图纸": "磨削", "检验项目": "粗糙度", "序号": "1"},
        ]), pd.DataFrame(), {}, {}, {})
        rule = copy.deepcopy(DEFAULT_RULES["过程检验表"])
        with self.assertRaises(ValueError):
            processor.validate_drawings(rule)
        for drawing in ("车削", "磨削"):
            rule["source_drawings"] = [drawing]
            processor.validate_drawings(rule)
            frame = processor.build("过程检验表", rule)
            self.assertEqual(frame["图纸"].tolist(), [drawing])
        rule["source_drawings"] = ["已删除图纸"]
        with self.assertRaises(ValueError):
            processor.validate_drawings(rule)

    def test_sheet_list_and_preview_work_without_office(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "template.xlsx"
            workbook = openpyxl.Workbook()
            workbook.active.title = "车削表"
            workbook.active["A1"] = "车削内容"
            workbook.create_sheet("磨削表")["B3"] = "磨削内容"
            workbook.save(path)
            workbook.close()
            app = ReportGeneratorApp.__new__(ReportGeneratorApp)
            app.template_path = Mock(get=Mock(return_value=str(path)))
            app.sheet_name_var = Mock(get=Mock(return_value="磨削表"))
            self.assertEqual(app.template_sheet_names(), ["车削表", "磨削表"])
            self.assertEqual(app.template_preview_rows()[2][1], "磨削内容")

    def test_individual_versions_are_written_to_each_report(self):
        first, second, versions = FakeWorksheet(), FakeWorksheet(), FakeWorksheet()
        for sheet in (first, second):
            sheet.Cells(1, 1).Value = "版本 {{报表版本}}"
            sheet.Cells(2, 1).Value = "检验项目"
        workbook = Mock()
        workbook.Sheets.side_effect = {"turning": first, "grinding": second, "报表版本信息": versions}.__getitem__
        @contextmanager
        def opened(_path):
            yield workbook
        with patch("report_system.core.engine.open_workbook", opened), patch(
                "report_system.core.engine.apply_rules_to_worksheet"):
            count = save_workbook_from_template("template.xlsx", "output.xlsx",
                {"turning": pd.DataFrame([{"检验项目": "外径"}]),
                 "grinding": pd.DataFrame([{"检验项目": "粗糙度"}])},
                {"turning": ("turning", 2, None), "grinding": ("grinding", 2, None)}, {}, {}, {},
                report_metadata={"turning": {"报表版本": "A"}, "grinding": {"报表版本": "B"}})
        self.assertEqual(count, 2)
        self.assertEqual(first.Cells(1, 1).Value, "版本 A")
        self.assertEqual(second.Cells(1, 1).Value, "版本 B")
        self.assertEqual(versions.Cells(2, 2).Value, "A")
        self.assertEqual(versions.Cells(3, 2).Value, "B")

    def test_import_config_embeds_settings_and_resolves_relative_template(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report_generator_config.json"
            config = {"rules": {"车削报告": {"report_version": "B", "source_drawings": ["车削"]}},
                      "template_profiles": {"默认": {"path": "template.xlsx", "sheet_config": {}}}}
            ConfigStore(path).save(config)
            (Path(folder) / "template.xlsx").write_bytes(b"template")
            app = ReportGeneratorApp.__new__(ReportGeneratorApp)
            app.template_library = TemplateLibrary(folder)
            app.template_catalog = []
            app.import_catalog_config(str(path))
            stored = app.template_catalog[0]["config"]
            self.assertEqual(stored["rules"]["车削报告"]["report_version"], "B")
            uploaded = Path(stored["template_profiles"]["默认"]["path"])
            self.assertEqual(uploaded.read_bytes(), b"template")
            self.assertNotEqual(uploaded, Path(folder) / "template.xlsx")
            app.config_file = str(Path(folder) / "current.json")
            app.load_config = Mock()
            app.apply_catalog_item(app.template_catalog[0])
            self.assertEqual(app.config_file, str(Path(folder) / "current.json"))
            app.load_config.assert_called_once_with(config_value=stored)
            self.assertEqual(len(app.template_catalog), 1)


if __name__ == "__main__":
    unittest.main()
