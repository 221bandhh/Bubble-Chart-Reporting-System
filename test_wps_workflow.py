import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from core.excel_com import Sheet
from data.product_repository import ProductRepository
from report_system.ui.app import ReportGeneratorApp
from ui.bubble_app import BubbleApp


class WpsWorkflowTests(unittest.TestCase):
    def test_bulk_append_uses_one_range(self):
        raw = Mock()
        sheet = Sheet(raw)
        sheet.append_rows([(1, 2), (3, 4)])
        raw.Range.assert_called_once_with('A1:B2')
        self.assertEqual(raw.Range.return_value.Value, ((1, 2), (3, 4)))

    def test_export_name_uses_current_date(self):
        repository = ProductRepository.__new__(ProductRepository)
        repository.product_dir = Mock(return_value=Path('products/A'))
        self.assertEqual(repository.export_path({}).name,
                         f'bubble_export（{date.today():%Y-%m-%d}）.xlsx')

    def test_snapshot_refresh_does_not_read_workbook(self):
        app = ReportGeneratorApp.__new__(ReportGeneratorApp)
        snapshot = {'frame': pd.DataFrame({'检验项目': ['外径']}),
                    'header': {'产品名': 'A'}, 'history': []}
        app.source_provider = lambda: snapshot
        app.source_path = Mock()
        app.status = Mock()
        app.source_tree = Mock()
        app._show_frame = Mock()
        with patch('report_system.ui.app.read_source_excel') as reader:
            app.refresh_product_source()
        reader.assert_not_called()
        self.assertEqual(app.df_source.iloc[0]['检验项目'], '外径')
        self.assertEqual(app._source_header, snapshot['header'])

    def test_failed_exit_export_keeps_window(self):
        app = BubbleApp.__new__(BubbleApp)
        app.product = {'name': 'A'}
        app._save_report_context = Mock(return_value=True)
        app.export_contract = Mock(side_effect=RuntimeError('WPS unavailable'))
        app.root = Mock()
        with patch('ui.bubble_app.messagebox.showerror'):
            app.on_close()
        app.root.destroy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
