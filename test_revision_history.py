import unittest

from core.product_info import REPORT_HEADER_FIELDS, append_revision, latest_revisions, revision_history
from report_system.core.history_layout import history_origin, write_history_block
from test_baobiaosys import FakeWorksheet


class RevisionHistoryTests(unittest.TestCase):
    def test_legacy_header_is_preserved_and_unchanged_save_is_not_duplicated(self):
        product = {"name": "A", "report_header": {"版本": "A"}}
        old = revision_history(product)[0]
        append_revision(product, {**old, "版本": "B"})
        append_revision(product, {**old, "版本": "B"})
        self.assertEqual([record["版本"] for record in product["report_history"]], ["A", "B"])

    def test_latest_three_follow_save_order(self):
        product = {"name": "A"}
        for version in ("A", "B", "C", "D"):
            append_revision(product, {"版本": version, "修改日期": "2020-01-01"})
        self.assertEqual([record["版本"] for record in latest_revisions(product["report_history"])], ["D", "C", "B"])

    def test_custom_location_and_unused_rows_are_cleared(self):
        sheet = FakeWorksheet()
        write_history_block(sheet, "K2", [{"版本": "B"}])
        self.assertEqual(sheet.Cells(2, 11).Value, REPORT_HEADER_FIELDS[0])
        self.assertEqual(sheet.Cells(3, 14).Value, "B")
        self.assertEqual(sheet.Cells(5, 14).Value, "")

    def test_data_overlap_and_invalid_coordinates_are_rejected(self):
        with self.assertRaises(ValueError):
            write_history_block(FakeWorksheet(), "A4", [], data_header=6, data_count=10)
        for value in ("A0", "A1:B3", "XFE1", "bad"):
            with self.assertRaises(ValueError):
                history_origin(value)
