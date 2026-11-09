import tempfile
import json
import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import openpyxl
import pandas as pd
from openpyxl.styles import PatternFill

from report_system.core.engine import save_workbook_from_template, DataProcessor, read_source_excel
from report_system.ui.app import ReportGeneratorApp


class XlsxExportTests(unittest.TestCase):
    def test_background_export_reports_success_and_failure_on_ui_poll(self):
        for error in (None, OSError("文件已被占用")):
            with self.subTest(error=error):
                app = ReportGeneratorApp.__new__(ReportGeneratorApp)
                app.root = Mock()
                app.status = Mock()
                thread = Mock()
                def make_thread(**kwargs):
                    thread.start.side_effect = kwargs["target"]
                    return thread
                with patch("report_system.ui.app.threading.Thread", side_effect=make_thread), patch(
                        "report_system.ui.app.save_workbook_from_template", side_effect=error), patch(
                        "report_system.ui.app.traceback.print_exc"), patch(
                        "report_system.ui.app.messagebox.showinfo") as success, patch(
                        "report_system.ui.app.messagebox.showerror") as failure:
                    app._start_generation("template.xlsx", "output.xlsx")
                    self.assertTrue(app._generating)
                    poll = app.root.after.call_args.args[1]
                    poll()
                    self.assertFalse(app._generating)
                    self.assertEqual(success.call_count, int(error is None))
                    self.assertEqual(failure.call_count, int(error is not None))

    def test_four_acceptance_cases_export_real_workbooks_without_office(self):
        root = Path(__file__).resolve().parent
        cases = root / "测试案例_四套"
        if not cases.exists():
            cases = root / "程序交付包" / "测试案例_四套"
        for folder in sorted(cases.glob("案例*")):
            if not folder.is_dir():
                continue
            with self.subTest(case=folder.name), tempfile.TemporaryDirectory() as temporary:
                config = json.loads((folder / "report_generator_config.json").read_text(encoding="utf-8"))
                expected = json.loads((folder / "预期结果.json").read_text(encoding="utf-8"))
                processor = DataProcessor(read_source_excel(folder / "bubble_export.xlsx"),
                    pd.DataFrame(config["freq"]), config["item_trans"], config["tool_ship"], config["tool_proc"])
                for profile in config["template_profiles"].values():
                    settings = profile["sheet_config"]
                    frames = {name: processor.build(name, rule) for name, rule in config["rules"].items()}
                    output = Path(temporary) / "report.xlsx"
                    template = folder / Path(profile["path"]).name
                    with contextlib.redirect_stdout(io.StringIO()), patch(
                            "report_system.core.engine.get_excel_app", side_effect=AssertionError("COM")):
                        save_workbook_from_template(str(template), str(output), frames,
                            {name: (value["sheet_name"], value["header"], value["footer"] or None)
                             for name, value in settings.items()}, {}, {}, {})
                    workbook = openpyxl.load_workbook(output)
                    try:
                        for name, frame in frames.items():
                            self.assertEqual(len(frame), expected[name]["rows"])
                            sheet = workbook[settings[name]["sheet_name"]]
                            start = settings[name]["header"] + 1
                            self.assertEqual([sheet.cell(start + i, 1).value for i in range(len(frame))],
                                             frame["图纸"].tolist())
                    finally:
                        workbook.close()

    def test_native_export_preserves_styles_merges_footer_versions_and_rules(self):
        with tempfile.TemporaryDirectory() as folder:
            template, output = Path(folder) / "template.xlsx", Path(folder) / "result.xlsx"
            workbook = openpyxl.Workbook()
            first = workbook.active
            first.title = "车削"
            first["A1"] = "版本 {{报表版本}}"
            first.merge_cells("A1:D1")
            for column, value in enumerate(("检验项目", "检验要求", "备注", "固定"), 1):
                first.cell(2, column, value)
            first["A3"].fill = PatternFill("solid", fgColor="FFFF00")
            first.row_dimensions[3].height = 30
            first["A4"] = "审核人"
            first.merge_cells("A4:D4")
            second = workbook.create_sheet("磨削")
            second.append(["检验项目", "检验要求"])
            second.append(["old", "old"])
            workbook.save(template)
            workbook.close()
            progress = []
            with patch("report_system.core.engine.get_excel_app", side_effect=AssertionError("COM must not be used")):
                count = save_workbook_from_template(
                    str(template), str(output),
                    {"车削": pd.DataFrame([{"检验项目": "外径", "检验要求": str(i)} for i in range(3)]),
                     "磨削": pd.DataFrame([{"检验项目": "粗糙度", "检验要求": "Ra1.6"}])},
                    {"车削": ("车削", 2, 4), "磨削": ("磨削", 1, None)}, {},
                    {"车削": {4: "固定值"}},
                    {"车削": [{"match_df_col": "检验项目", "match_value": "外径",
                                "target_col": 3, "fill_value": "命中"}]},
                    report_metadata={"车削": {"报表版本": "A"}, "磨削": {"报表版本": "B"}},
                    report_header={"产品名": "测试产品"},
                    history_layouts={"车削": {"start": "A1", "sheet": "修订"}},
                    report_history=[{"版本": "C"}], progress=progress.append)
            self.assertEqual(count, 2)
            result = openpyxl.load_workbook(output)
            try:
                sheet = result["车削"]
                self.assertEqual(sheet["A1"].value, "版本 A")
                self.assertEqual(sheet["A6"].value, "审核人")
                self.assertIn("A6:D6", {str(area) for area in sheet.merged_cells.ranges})
                for row in range(3, 6):
                    self.assertEqual(sheet.cell(row, 3).value, "命中")
                    self.assertEqual(sheet.cell(row, 4).value, "固定值")
                    self.assertEqual(sheet.cell(row, 1).fill.fgColor.rgb, "00FFFF00")
                    self.assertEqual(sheet.row_dimensions[row].height, 30)
                self.assertEqual(result["磨削"]["A2"].value, "粗糙度")
                self.assertEqual(result["报表版本信息"]["B3"].value, "B")
                self.assertEqual(result["报表表头"]["B1"].value, "测试产品")
                self.assertEqual(result["修订"]["D2"].value, "C")
                self.assertEqual(progress[-1], "正在保存报表...")
            finally:
                result.close()

    def test_failed_export_does_not_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            template, output = Path(folder) / "template.xlsx", Path(folder) / "result.xlsx"
            workbook = openpyxl.Workbook()
            workbook.save(template)
            workbook.close()
            output.write_bytes(b"existing report")
            with self.assertRaises(ValueError):
                save_workbook_from_template(str(template), str(output),
                    {"missing": pd.DataFrame([{"检验项目": "外径"}])}, {}, {}, {}, {})
            self.assertEqual(output.read_bytes(), b"existing report")


if __name__ == "__main__":
    unittest.main()
