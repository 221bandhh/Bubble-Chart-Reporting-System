import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import openpyxl

from report_system.core.template_preview import cell_address, parse_header_cells, preview_header_cells
from report_system.ui.app import ReportGeneratorApp


class TemplatePositionTests(unittest.TestCase):
    def test_parse_addresses_and_reject_invalid_ranges(self):
        self.assertEqual(parse_header_cells("产品名=$b$2，版本=F3", ("产品名", "版本")),
                         {"产品名": "B2", "版本": "F3"})
        for address in ("A0", "A1:B2", "Sheet1!A1", "XFE1", "A1048577"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                cell_address(address)
        self.assertEqual(cell_address("XFD1048576"), "XFD1048576")

    def test_preview_shows_exact_position_neighbors_and_merged_anchor(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "template.xlsx"
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.title = "首件表"
            sheet.merge_cells("B2:D2")
            sheet["B2"] = "产品名称：{{产品名}}"
            sheet["A1"] = "周边说明"
            sheet["BH320"] = "远处的版本位置"
            workbook.save(path)
            workbook.close()
            original = path.read_bytes()
            result = preview_header_cells(path, "首件表", {"产品名": "C2", "版本": "BH320"})
            self.assertEqual(result[0]["anchor"], "B2")
            self.assertEqual(result[0]["value"], "产品名称：{{产品名}}")
            self.assertEqual(result[0]["rows"][0][1][0], "周边说明")
            self.assertEqual((result[1]["row"], result[1]["column"]), (320, 60))
            self.assertEqual(result[1]["value"], "远处的版本位置")
            self.assertEqual(path.read_bytes(), original)

    def test_sheet_choices_refresh_on_template_change_and_keep_valid_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = []
            for filename, names in (("a.xlsx", ["首件", "出货"]), ("b.xlsx", ["过程", "修订"])):
                path = Path(temporary) / filename
                workbook = openpyxl.Workbook()
                workbook.active.title = names[0]
                workbook.create_sheet(names[1])
                workbook.save(path)
                workbook.close()
                paths.append(path)
            app = ReportGeneratorApp.__new__(ReportGeneratorApp)
            app.template_path = MagicMock()
            app.sheet_name_var = MagicMock()
            app.sheet_selector = {}
            app.template_path.get.return_value = str(paths[0])
            app.sheet_name_var.get.return_value = "出货"
            app.refresh_template_sheets()
            self.assertEqual(app.sheet_selector["values"], ["首件", "出货"])
            app.sheet_name_var.set.assert_not_called()
            app.template_path.get.return_value = str(paths[1])
            app.refresh_template_sheets()
            self.assertEqual(app.sheet_selector["values"], ["过程", "修订"])
            app.sheet_name_var.set.assert_called_once_with("过程")
