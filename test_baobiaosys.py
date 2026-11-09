import copy
import unittest
from types import SimpleNamespace

import pandas as pd

from baobiaosys import (
    DEFAULT_RULES,
    DataProcessor,
    apply_rules_to_worksheet,
    smart_column_mapping,
)


class FakeCell:
    def __init__(self):
        self.Value = None


class FakeWorksheet:
    def __init__(self):
        self.UsedRange = SimpleNamespace(
            Row=1,
            Column=1,
            Rows=SimpleNamespace(Count=2),
            Columns=SimpleNamespace(Count=5),
        )
        self.cells = {}

    def Cells(self, row, column):
        return self.cells.setdefault((row, column), FakeCell())


class DataProcessorTests(unittest.TestCase):
    def test_process_report_keeps_chinese_fields_and_adds_patrol(self):
        source = pd.DataFrame([{
            "序号": "1", "检验项目": "外径", "检验要求": "10mm",
            "测量器具": "卡尺", "重要度": "▲", "备注": "",
        }])
        frequency = pd.DataFrame([{
            "特性符号": "▲", "分类": "现场", "样件检验频次": "首中末检",
            "样件n": "5", "量产检验频次": "首中末检", "量产n": "5",
        }])
        processor = DataProcessor(
            source, frequency, {"外径": "Outer Diameter"},
            {"卡尺": "Caliper"}, {"卡尺": "Caliper / Operator"},
        )
        rules = copy.deepcopy(DEFAULT_RULES["过程检验表"])
        result = processor.build("过程检验表", rules)
        self.assertEqual(len(result), 2)
        self.assertEqual(result.iloc[0]["检验项目"], "外径")
        self.assertEqual(result.iloc[0]["检验项目翻译"], "Outer Diameter")
        self.assertEqual(result.iloc[0]["样件n"], 5)
        self.assertEqual(result.iloc[1]["检测场地"], "巡检")

    def test_special_shipping_row_survives_deduplication(self):
        source = pd.DataFrame([
            {"序号": "1.1", "检验项目": "螺纹", "检验要求": "普通"},
            {"序号": "1.2", "检验项目": "螺纹", "检验要求": "GN"},
            {"序号": "1.3", "检验项目": "螺纹", "检验要求": "普通"},
        ])
        processor = DataProcessor(source, pd.DataFrame(), {}, {}, {})
        rules = copy.deepcopy(DEFAULT_RULES["出货检验表"])
        rules["thread_merge"] = False
        result = processor.build("出货检验表", rules)
        self.assertEqual(result["检验要求"].tolist(), ["普通", "GN"])

    def test_shipping_dedup_does_not_cross_drawings(self):
        source = pd.DataFrame([
            {"图纸": "A", "序号": "1", "检验项目": "外径", "检验要求": "10"},
            {"图纸": "B", "序号": "1", "检验项目": "外径", "检验要求": "20"},
        ])
        processor = DataProcessor(source, pd.DataFrame(), {}, {}, {})
        rules = copy.deepcopy(DEFAULT_RULES["出货检验表"])
        rules["thread_merge"] = False
        result = processor.build("出货检验表", rules)
        self.assertEqual(result["图纸"].tolist(), ["A", "B"])


class WorksheetTests(unittest.TestCase):
    def test_condition_writes_unmapped_target_and_fixed_column(self):
        sheet = FakeWorksheet()
        frame = pd.DataFrame([{"检验项目": "外径"}], index=[42])
        apply_rules_to_worksheet(
            sheet, 1, None, frame, {"检验项目": 1}, {4: "固定"},
            [{"match_df_col": "检验项目", "match_type": "等于",
              "match_value": "外径", "target_col": 3, "fill_value": "命中"}],
        )
        self.assertEqual(sheet.Cells(2, 1).Value, "外径")
        self.assertEqual(sheet.Cells(2, 3).Value, "命中")
        self.assertEqual(sheet.Cells(2, 4).Value, "固定")

    def test_duplicate_headers_can_map_to_distinct_columns(self):
        result = smart_column_mapping(
            ["判定_1", "判定_2"], ["判定", "判定"]
        )
        self.assertEqual(result, {"判定_1": 1, "判定_2": 2})


if __name__ == "__main__":
    unittest.main()
