from pathlib import Path
import json
import unittest
from io import StringIO
import openpyxl
import pandas as pd
from report_system.core.engine import DataProcessor, BUILT_IN_FREQ, clean_frame, read_source_excel


class FourAcceptanceFixtureTests(unittest.TestCase):
    def test_all_four_cases_have_valid_templates_routing_and_versions(self):
        root = Path(__file__).resolve().parent
        cases = root / '测试案例_四套'
        manifest = json.loads((cases / '案例清单与验证结果.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest), 4)
        for case in manifest:
            with self.subTest(case=case['case']):
                folder = cases / case['case']
                config = json.loads((folder / 'report_generator_config.json').read_text(encoding='utf-8'))
                expected = json.loads((folder / '预期结果.json').read_text(encoding='utf-8'))
                frame = read_source_excel(folder / 'bubble_export.xlsx')
                self.assertEqual(len(frame), case['source_rows'])
                processor = DataProcessor(frame, clean_frame(pd.DataFrame(config['freq'])),
                    config['item_trans'], config['tool_ship'], config['tool_proc'])
                versions = []
                for profile in config['template_profiles'].values():
                    workbook = openpyxl.load_workbook(profile['path'], read_only=True)
                    try:
                        targets = []
                        for name, rule in config['rules'].items():
                            processor.validate_drawings(rule)
                            result = processor.build(name, rule)
                            self.assertEqual(len(result), expected[name]['rows'])
                            self.assertEqual(set(result['图纸']), set(expected[name]['source_drawings']))
                            item = profile['sheet_config'][name]
                            self.assertIn(item['sheet_name'], workbook.sheetnames)
                            self.assertEqual(workbook[item['sheet_name']].cell(item['header'], 1).value, '图纸')
                            targets.append(item['sheet_name'])
                        self.assertEqual(len(targets), len(set(targets)))
                    finally:
                        workbook.close()
                versions = [rule['report_version'] for rule in config['rules'].values()]
                self.assertEqual(len(versions), len(set(versions)))
                product = json.loads((folder / 'product.json').read_text(encoding='utf-8'))
                for drawing in product['drawings']:
                    self.assertTrue((folder / drawing['path']).is_file())

    def test_invalid_drawing_fixtures_are_rejected(self):
        folder = Path(__file__).resolve().parent / '测试案例_四套/案例04-边界与异常'
        processor = DataProcessor(read_source_excel(folder / 'bubble_export.xlsx'), pd.DataFrame(), {}, {}, {})
        for filename in ('异常1_未指定图纸.json', '异常2_图纸不存在.json'):
            with self.subTest(filename=filename):
                config = json.loads((folder / filename).read_text(encoding='utf-8'))
                with self.assertRaises(ValueError):
                    processor.validate_drawings(next(iter(config['rules'].values())))
        config = json.loads((folder / '异常3_多个报表同Sheet.json').read_text(encoding='utf-8'))
        targets = [v['sheet_name'] for v in config['template_profiles']['标准模板']['sheet_config'].values()]
        self.assertLess(len(set(targets)), len(targets))


if __name__ == '__main__':
    unittest.main()
