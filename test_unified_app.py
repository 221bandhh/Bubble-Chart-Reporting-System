import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from data.excel_contract import export_product
from report_system.core.engine import read_source_excel
from report_system.ui.app import ReportGeneratorApp
from ui.bubble_app import BubbleApp


class UnifiedWorkflowTests(unittest.TestCase):
    def test_report_button_selects_embedded_page(self):
        app = BubbleApp.__new__(BubbleApp)
        app.product = {"id": "A"}
        app.main_tabs = Mock()
        app.report_page = Mock()
        app._ensure_report_context = Mock()
        app.open_report_tool()
        app.main_tabs.select.assert_called_once_with(app.report_page)
        app._ensure_report_context.assert_called_once()

    def test_batch_product_import_continues_after_one_file_fails(self):
        app = BubbleApp.__new__(BubbleApp)
        app.root = Mock()
        app.product = None
        app.repository = Mock()
        first, last = {"id": "first"}, {"id": "last"}
        app.repository.import_product.side_effect = [first, ValueError("invalid product"), last]
        app._save_report_context = Mock(return_value=True)
        app._save_product = Mock()
        app._release_report_context = Mock()
        app._refresh_products = Mock()
        paths = ("one.json", "bad.json", "three.json")
        with patch("ui.bubble_app.filedialog.askopenfilenames", return_value=paths), \
             patch("ui.bubble_app.messagebox.showwarning") as warning:
            app.import_product()
        self.assertEqual(app.repository.import_product.call_count, 3)
        app._refresh_products.assert_called_once_with("last")
        warning.assert_called_once()

    def test_product_data_refreshes_before_each_processing(self):
        with tempfile.TemporaryDirectory() as folder:
            product = {"name": "A", "drawings": [{"name": "图1", "bubbles": [
                {"seq": 1, "item": "外径", "req": "10", "tool": "卡尺"}]}]}
            app = ReportGeneratorApp.__new__(ReportGeneratorApp)
            app.source_provider = lambda: export_product(product, Path(folder) / "bubble_export.xlsx")
            app.load_source = lambda path, **kwargs: setattr(app, "df_source", read_source_excel(path))
            app._store_rule_form = Mock()
            app.sync_dictionaries = Mock()
            app.freq_df = pd.DataFrame()
            app.item_trans = app.tool_ship = app.tool_proc = {}
            first = app._processor()
            self.assertEqual(first.df.iloc[0]["检验要求"], "10")
            product["drawings"][0]["bubbles"][0]["req"] = "20"
            second = app._processor()
            self.assertEqual(second.df.iloc[0]["检验要求"], "20")

    def test_failed_report_save_can_cancel_product_switch(self):
        app = BubbleApp.__new__(BubbleApp)
        app.report_app = Mock()
        app.report_app.save_config.return_value = False
        with patch("ui.bubble_app.messagebox.askyesno", return_value=False):
            self.assertFalse(app._save_report_context())

    def test_releasing_report_clears_data_and_widgets(self):
        app = BubbleApp.__new__(BubbleApp)
        report = Mock()
        app.report_app = report
        app.report_page = Mock()
        child = Mock()
        app.report_page.winfo_children.return_value = [child]
        app._release_report_context()
        self.assertIsNone(report.df_source)
        self.assertIsNone(app.report_app)
        child.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
