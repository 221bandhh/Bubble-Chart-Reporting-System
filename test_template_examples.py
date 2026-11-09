import json
import unittest
from pathlib import Path

import openpyxl

from report_system.data.template_library import TemplateLibrary


class TemplateExampleTests(unittest.TestCase):
    def test_new_examples_are_registered_and_exported(self):
        root = Path(__file__).resolve().parent
        cases = root / "模板案例库_新增四套"
        items = TemplateLibrary(root).list_items()
        examples = [item for item in items if item.get("example_code", "").startswith("template-example-20261023-")]
        self.assertEqual(len(examples), 4)
        for item in examples:
            folder = cases / item["process"]
            with self.subTest(example=item["name"]):
                expected = json.loads((folder / "预期结果.json").read_text(encoding="utf-8"))
                config = item["config"]
                self.assertTrue(Path(config["templates"]["path"]).is_file())
                workbook = openpyxl.load_workbook(folder / "生成结果示例.xlsx", read_only=True)
                try:
                    for name, count in expected.items():
                        self.assertGreater(count, 0)
                        settings = config["sheet_config"][name]
                        sheet = workbook[settings["sheet_name"]]
                        start = settings["header"] + 1
                        values = [sheet.cell(start + i, 1).value for i in range(count)]
                        self.assertEqual(values, config["rules"][name]["source_drawings"] * count)
                        self.assertEqual(sheet.cell(start, 9).value, item["material"])
                finally:
                    workbook.close()
                portable = json.loads((folder / "可导入模板配置.json").read_text(encoding="utf-8"))
                self.assertEqual(portable["templates"]["path"], "template.xlsx")


if __name__ == "__main__":
    unittest.main()
