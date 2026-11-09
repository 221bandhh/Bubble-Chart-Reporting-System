import tempfile
import unittest
from pathlib import Path

import openpyxl

from core.bubble_engine import BubbleEngine, BubbleError, sequence_label
from data.excel_contract import CONTRACT_SHEET, export_product
from data.product_repository import ProductRepository
from data.gauge_library import GaugeLibrary


class BubbleEngineTests(unittest.TestCase):
    def test_sequence_conflict_is_rejected(self):
        engine = BubbleEngine([{"seq": 1, "x": 10, "y": 20}])
        with self.assertRaises(BubbleError):
            engine.add(30, 40, seq="1.0")

    def test_undo_restores_add_update_and_delete(self):
        engine = BubbleEngine(history_limit=3)
        bubble = engine.add(10, 20)
        engine.update(bubble["seq"], {"item": "外径"})
        engine.delete(bubble["seq"])
        self.assertTrue(engine.undo())
        self.assertEqual(engine.get(1)["item"], "外径")
        self.assertTrue(engine.undo())
        self.assertEqual(engine.get(1)["item"], "")
        self.assertTrue(engine.undo())
        self.assertEqual(engine.bubbles, [])

    def test_child_sequence_is_single_history_operation(self):
        engine = BubbleEngine([{"seq": 4, "x": 10, "y": 20}])
        child = engine.add_child(4, 30, 40)
        self.assertEqual(sequence_label(child["seq"]), "4.1")
        self.assertEqual(engine.history_size, 1)
        engine.undo()
        self.assertIsNone(engine.get("4.1"))

    def test_history_has_upper_bound(self):
        engine = BubbleEngine(history_limit=2)
        engine.add(1, 1)
        engine.add(2, 2)
        engine.add(3, 3)
        self.assertEqual(engine.history_size, 2)


    def test_gauge_records_round_trip_with_legacy_defaults(self):
        engine = BubbleEngine([{"seq": 1, "x": 5, "y": 6, "gauges": [{"name": "Bore gauge", "spec": "0-25", "part_no": "BG-1"}]},
                              {"seq": 2, "x": 7, "y": 8}])
        self.assertEqual(engine.get(1)["gauges"], [{"name": "Bore gauge", "spec": "0-25", "part_no": "BG-1"}])
        self.assertEqual(engine.get(2)["gauges"], [])

class ProductStorageTests(unittest.TestCase):
    def test_products_are_stored_in_separate_folders(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = ProductRepository(folder)
            first = repository.create("产品A")
            second = repository.create("产品B")
            self.assertNotEqual(first["id"], second["id"])
            self.assertTrue((Path(folder) / "products" / "产品A" / "product.json").is_file())
            self.assertTrue((Path(folder) / "products" / "产品B" / "product.json").is_file())

    def test_shared_gauge_history_deduplicates_and_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = GaugeLibrary(folder), GaugeLibrary(folder)
            first.remember([{"name": "Bore gauge", "spec": "0-25", "part_no": "BG-1"}])
            second.remember([{"name": "bore gauge", "spec": "0-25", "part_no": "BG-1"}])
            self.assertEqual(len(first.list_items()), 1)
            self.assertEqual(first.list_items()[0]["part_no"], "BG-1")

    def test_excel_contract_contains_all_drawings(self):
        with tempfile.TemporaryDirectory() as folder:
            product = {
                "id": "demo", "name": "产品A",
                "drawings": [
                    {"name": "图纸1", "bubbles": [{"seq": 1, "item": "外径", "req": "10", "tool": "卡尺", "x": 5, "y": 6}]},
                    {"name": "图纸2", "bubbles": [{"seq": 2, "item": "长度", "req": "20", "tool": "卡尺", "x": 7, "y": 8}]},
                ],
            }
            output = export_product(product, Path(folder) / "bubble_export.xlsx")
            workbook = openpyxl.load_workbook(output, read_only=True, data_only=True)
            try:
                rows = list(workbook[CONTRACT_SHEET].iter_rows(values_only=True))
            finally:
                workbook.close()
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[1][0:3], ("产品A", "图纸1", "1"))
            self.assertEqual(rows[2][0:3], ("产品A", "图纸2", "2"))


if __name__ == "__main__":
    unittest.main()

