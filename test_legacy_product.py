import json
import tempfile
import unittest
from pathlib import Path

from data.product_repository import ProductRepository
from data.excel_contract import export_product
from report_system.core.engine import read_source_excel


class LegacyProductTests(unittest.TestCase):
    def raw(self):
        return {"id": "old-id", "name": "旧零件", "image_path": "drawing.png",
                "bubbles": [{"seq": "1.1", "x": 10, "y": 20, "item": "外径",
                             "req": "10", "internal": "9.95", "tool": "卡尺"}],
                "report_header": {"版本": "B"}, "font_size": 17}

    def write_source(self, source, raw):
        source = Path(source)
        (source / "drawing.png").write_bytes(b"original image")
        path = source / "product.json"
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8-sig")
        return path

    def test_import_single_drawing_keeps_metadata_and_original_files(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as source:
            path = self.write_source(source, self.raw())
            original = path.read_bytes()
            repository = ProductRepository(workspace)
            product = repository.import_product(path)
            self.assertNotEqual(product["id"], "old-id")
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(product["report_header"], {"版本": "B"})
            self.assertEqual(product["font_size"], 17)
            drawing = product["drawings"][0]
            self.assertEqual(drawing["bubbles"][0]["internal"], "9.95")
            self.assertEqual(drawing["bubbles"][0]["seq"], 1.1)
            self.assertEqual(repository.drawing_path(product, drawing).read_bytes(), b"original image")
            self.assertEqual((repository.product_dir(product) / "imported_product.original.json").read_bytes(), original)
            Path(source, "drawing.png").unlink()
            loaded = repository.load(product["id"])
            frame = read_source_excel(export_product(loaded, repository.export_path(loaded)))
            self.assertEqual(str(frame.iloc[0]["内控要求"]), "9.95")

    def test_common_single_drawing_keys_and_nested_descriptor(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as source:
            repository = ProductRepository(workspace)
            for key in ("path", "image_path", "drawing_path", "image_file", "image", "drawing"):
                with self.subTest(key=key):
                    raw = self.raw()
                    del raw["image_path"]
                    raw[key] = "drawing.png"
                    path = self.write_source(source, raw)
                    product = repository.import_product(path)
                    self.assertEqual(len(product["drawings"]), 1)
                    self.assertEqual(len(product["drawings"][0]["bubbles"]), 1)
            raw = self.raw()
            raw["drawing"] = {"path": raw.pop("image_path"), "bubbles": raw.pop("bubbles"), "name": "工序1"}
            product = repository.import_product(self.write_source(source, raw))
            self.assertEqual(product["drawings"][0]["name"], "工序1")

    def test_existing_indexed_single_drawing_is_read_and_backed_up_on_save(self):
        with tempfile.TemporaryDirectory() as workspace:
            repository = ProductRepository(workspace)
            entry = repository.create("旧零件")
            path = self.write_source(repository.product_dir(entry), self.raw())
            original = path.read_bytes()
            loaded = repository.load(entry["id"])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(loaded["id"], entry["id"])
            loaded["drawings"][0]["bubbles"][0]["req"] = "11"
            repository.save(loaded)
            backup = path.with_name("product.legacy.bak.json")
            self.assertEqual(backup.read_bytes(), original)
            repository.save(loaded)
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(repository.load(entry["id"])["drawings"][0]["bubbles"][0]["req"], "11")

    def test_old_absolute_path_can_be_repaired_from_adjacent_image(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as source:
            raw = self.raw()
            raw["image_path"] = "Z:/previous-computer/drawing.png"
            path = self.write_source(source, raw)
            product = ProductRepository(workspace).import_product(path)
            self.assertEqual(len(product["drawings"][0]["bubbles"]), 1)

    def test_missing_image_is_not_silently_discarded_and_can_be_reselected(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as source:
            raw = self.raw()
            raw.pop("image_path")
            path = self.write_source(source, raw)
            repository = ProductRepository(workspace)
            with self.assertRaises(FileNotFoundError):
                repository.import_product(path)
            self.assertEqual(repository.list_products(), [])
            product = repository.import_product(path, image_path=Path(source) / "drawing.png")
            self.assertEqual(len(product["drawings"][0]["bubbles"]), 1)

    def test_duplicate_sequences_are_rejected_without_partial_product(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as source:
            raw = self.raw()
            raw["bubbles"].append(raw["bubbles"][0].copy())
            repository = ProductRepository(workspace)
            with self.assertRaises(ValueError):
                repository.import_product(self.write_source(source, raw))
            self.assertEqual(repository.list_products(), [])
            self.assertEqual(list(repository.products_dir.glob("*/product.json")), [])

    def test_import_named_product_and_append_process_preserves_existing_data(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as source:
            repository = ProductRepository(workspace)
            path = self.write_source(source, self.raw())
            product = repository.import_product(path, name="指定产品名")
            first = product["drawings"][0].copy()
            product["report_header"] = {"版本": "C"}
            repository.save(product)
            result = repository.import_product(path, target_product=product, drawing_name="精加工")
            loaded = repository.load(product["id"])
            self.assertIs(result, product)
            self.assertEqual(len(repository.list_products()), 1)
            self.assertEqual(loaded["name"], "指定产品名")
            self.assertEqual(loaded["report_header"], {"版本": "C"})
            self.assertEqual(loaded["drawings"][0], first)
            self.assertEqual(loaded["drawings"][1]["name"], "精加工")
            self.assertNotEqual(loaded["drawings"][1]["id"], first["id"])
            self.assertEqual(loaded["drawings"][1]["bubbles"], first["bubbles"])


if __name__ == "__main__":
    unittest.main()
