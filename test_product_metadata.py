import json
import tempfile
import unittest
from pathlib import Path

import openpyxl

from data.product_repository import ProductRepository
from data.excel_contract import export_product


class ProductMetadataTests(unittest.TestCase):
    def test_old_id_folder_migrates_and_preserves_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "products"
            (root / "old-id").mkdir(parents=True)
            (root / "index.json").write_text(json.dumps({"products": [{"id": "old-id", "name": "零件A"}]}), encoding="utf-8")
            (root / "old-id" / "product.json").write_text(json.dumps({"id": "old-id", "name": "零件A", "drawings": []}), encoding="utf-8")
            (root / "old-id" / "report_generator_config.json").write_text("{}", encoding="utf-8")
            repository = ProductRepository(directory)
            self.assertTrue((root / "零件A" / "report_generator_config.json").exists())
            self.assertEqual(repository.load("old-id")["name"], "零件A")

    def test_duplicate_names_have_distinct_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = ProductRepository(directory)
            first = repository.create("产品A")
            second = repository.create("产品A")
            self.assertNotEqual(repository.product_dir(first), repository.product_dir(second))

    def test_metadata_is_separate_from_size_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            product = {"name": "产品A", "drawings": [], "report_header": {"版本": "B", "修改人": "张三"}}
            path = export_product(product, Path(directory) / "export.xlsx")
            workbook = openpyxl.load_workbook(path, read_only=True)
            try:
                values = dict(workbook["报表表头"].iter_rows(values_only=True))
                self.assertEqual(values["版本"], "B")
                self.assertEqual(values["产品名"], "产品A")
                self.assertEqual(workbook["气泡数据"].max_row, 1)
            finally:
                workbook.close()
