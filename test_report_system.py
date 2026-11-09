import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from report_system.core.engine import DEFAULT_RULES, DataProcessor, read_source_excel
from report_system.ui.app import ReportGeneratorApp
from data.excel_contract import export_product


class ReportWindowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.folder.cleanup()
            self.skipTest(f"Tk runtime unavailable: {exc}")
        self.root.withdraw()
        with patch.object(ReportGeneratorApp, "load_config"):
            self.app = ReportGeneratorApp(self.root)
        self.app.config_file = str(Path(self.folder.name) / "config.json")

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        self.folder.cleanup()

    def test_empty_source_and_blank_optional_counts_can_close(self):
        self.app.rule_fields["patrol_n"].set("")
        self.app.rule_fields["patrol_mass_n"].set("")
        self.app.on_close()
        self.assertTrue(Path(self.app.config_file).is_file())

    def test_invalid_configuration_can_be_discarded_on_close(self):
        self.app.header_var.set("invalid")
        with patch("report_system.ui.app.messagebox.askyesno", return_value=True) as confirm:
            self.app.on_close()
        confirm.assert_called_once()

    def test_custom_reports_profiles_survive_reload(self):
        self.app.rules["自定义过程"] = copy.deepcopy(DEFAULT_RULES["过程检验表"])
        self.app.rules["自定义过程"]["base_type"] = "过程检验表"
        self.app.sheet_config["自定义过程"] = {"sheet_name": "自定义过程", "header": 2, "footer": 0}
        with patch("report_system.ui.app.simpledialog.askstring", return_value="第二模板"):
            self.app.add_profile()
        self.app.template_path.set("second.xlsx")
        self.assertTrue(self.app.save_config())
        self.app.load_config()
        self.assertIn("自定义过程", self.app.report_types)
        self.assertEqual(self.app.active_template_profile, "第二模板")
        self.assertEqual(self.app.template_path.get(), "second.xlsx")
        self.assertEqual(self.app.template_profiles["默认模板"]["sheet_config"]["自定义过程"]["header"], 2)


class ReportContractTests(unittest.TestCase):
    def test_close_does_not_require_loaded_source(self):
        app = ReportGeneratorApp.__new__(ReportGeneratorApp)
        app.root = Mock()
        app.df_source = None
        app.save_config = Mock(return_value=True)
        app.on_close()
        app.root.destroy.assert_called_once()

    def test_failed_save_can_close_without_tk(self):
        app = ReportGeneratorApp.__new__(ReportGeneratorApp)
        app.root = Mock()
        app.save_config = Mock(return_value=False)
        with patch("report_system.ui.app.messagebox.askyesno", return_value=True):
            app.on_close()
        app.root.destroy.assert_called_once()

    def test_contract_round_trip_with_empty_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = export_product({"name": "A", "drawings": []}, Path(folder) / "bubble_export.xlsx")
            frame = read_source_excel(path)
            self.assertTrue(frame.empty)
            self.assertIn("检验项目", frame.columns)

    def test_custom_process_report_inherits_patrol_behavior(self):
        source = pd.DataFrame([{"序号": "1", "检验项目": "外径", "测量器具": "卡尺", "重要度": "▲"}])
        rule = copy.deepcopy(DEFAULT_RULES["过程检验表"])
        rule["base_type"] = "过程检验表"
        frame = DataProcessor(source, pd.DataFrame(), {}, {}, {}).build("新增过程", rule)
        self.assertEqual(frame["检测场地"].tolist(), ["现场", "巡检"])


if __name__ == "__main__":
    unittest.main()
