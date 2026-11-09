import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import openpyxl

from report_system.data.config_store import ConfigStore
from report_system.data.template_library import TemplateLibrary
from report_system.ui.app import ReportGeneratorApp


class TemplateLibraryTests(unittest.TestCase):
    def test_readable_names_are_safe_and_same_names_stay_separate(self):
        with tempfile.TemporaryDirectory() as workspace:
            library = TemplateLibrary(workspace)
            template = self.template(workspace)
            first = library.add({'name': '出货/检验:模板', 'path': str(template)})
            second = library.add({'name': '出货/检验:模板', 'path': str(template)})
            folder = Path(first['path']).parent
            self.assertTrue(folder.name.startswith('出货_检验_模板_'))
            self.assertNotEqual(folder, Path(second['path']).parent)

    def test_old_folders_migrate_with_catalog_and_product_references(self):
        with tempfile.TemporaryDirectory() as workspace:
            library = TemplateLibrary(workspace)
            template = self.template(workspace)
            item = library.add({'name': '车削首件', 'config': {
                'templates': {'path': str(template)}}})
            folder = Path(item['path']).parent
            old = folder.with_name(item['id'])
            folder.rename(old)
            catalog = library.store.load()

            def old_paths(value):
                if isinstance(value, dict):
                    return {key: old_paths(part) for key, part in value.items()}
                if isinstance(value, list):
                    return [old_paths(part) for part in value]
                if isinstance(value, str):
                    return value.replace(folder.name, old.name)
                return value

            library.store.save(old_paths(catalog))
            config_path = old / 'report_generator_config.json'
            ConfigStore(config_path).save(old_paths(ConfigStore(config_path).load()))
            product_config = Path(workspace) / 'products' / 'A' / 'report_generator_config.json'
            ConfigStore(product_config).save(old_paths(item['config']))
            migrated = TemplateLibrary(workspace).list_items()[0]
            self.assertFalse(old.exists())
            self.assertTrue(Path(migrated['path']).is_file())
            workbook = migrated['config']['templates']['path']
            self.assertTrue(Path(workbook).is_file())
            self.assertEqual(ConfigStore(product_config).load()['templates']['path'], workbook)
            self.assertEqual(ConfigStore(migrated['path']).load()['templates']['path'], workbook)
            self.assertEqual(TemplateLibrary(workspace).list_items(), [migrated])

    def template(self, directory):
        path = Path(directory) / "template.xlsx"
        workbook = openpyxl.Workbook()
        workbook.active["A1"] = "检验项目"
        workbook.save(path)
        workbook.close()
        return path

    def test_other_products_see_upload_and_original_can_be_removed(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as source:
            template = self.template(source)
            first, second = TemplateLibrary(workspace), TemplateLibrary(workspace)
            item = first.add({"name": "共享模板", "path": str(template)})
            template.unlink()
            self.assertEqual(second.list_items()[0]["id"], item["id"])
            workbook = openpyxl.load_workbook(second.list_items()[0]["path"])
            self.assertEqual(workbook.active["A1"].value, "检验项目")
            workbook.close()

    def test_current_product_upload_keeps_rules_and_metadata_edit_preserves_config(self):
        with tempfile.TemporaryDirectory() as workspace:
            product = Path(workspace) / "products" / "产品A"
            product.mkdir(parents=True)
            template = self.template(product)
            config = {"rules": {"过程": {"source_drawings": ["车削"], "report_version": "B"}},
                      "template_profiles": {"默认": {"path": "template.xlsx", "sheet_config": {}}},
                      "templates": {"path": "template.xlsx"}, "template_catalog": [{"name": "old"}]}
            app = ReportGeneratorApp.__new__(ReportGeneratorApp)
            app.config_file = str(product / "report_generator_config.json")
            ConfigStore(app.config_file).save(config)
            app.save_config = Mock(return_value=True)
            app.template_library = TemplateLibrary(workspace)
            app.upload_current_template({"name": "产品A模板", "process": "车削"})
            library = TemplateLibrary(workspace)
            item = library.list_items()[0]
            self.assertNotIn("template_catalog", item["config"])
            self.assertEqual(item["config"]["rules"], config["rules"])
            library.update_metadata(item["id"], {"name": "通用车削", "material": "钢", "path": "wrong"})
            updated = library.list_items()[0]
            self.assertEqual(updated["name"], "通用车削")
            self.assertEqual(updated["config"], item["config"])
            self.assertEqual(updated["path"], item["path"])
            template.unlink()
            self.assertTrue(Path(updated["config"]["templates"]["path"]).is_file())
            self.assertEqual(ConfigStore(app.config_file).load(), config)

    def test_library_can_move_to_another_workspace(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            template = self.template(first)
            original = TemplateLibrary(first)
            original.add({"name": "模板", "config": {
                "rules": {}, "templates": {"path": str(template)}}})
            shutil.move(str(original.root), str(Path(second) / "template_library"))
            item = TemplateLibrary(second).list_items()[0]
            self.assertTrue(Path(item["path"]).is_file())
            self.assertTrue(Path(item["config"]["templates"]["path"]).is_file())
            self.assertTrue(Path(item["path"]).is_relative_to(Path(second)))

    def test_deleted_entry_stays_deleted_after_legacy_migration(self):
        with tempfile.TemporaryDirectory() as workspace:
            template = self.template(workspace)
            library = TemplateLibrary(workspace)
            source = Path(workspace) / "report_generator_config.json"
            items = [{"name": "旧模板", "path": "template.xlsx"}]
            library.migrate_legacy(source, items)
            library.migrate_legacy(source, items)
            self.assertEqual(len(library.list_items()), 1)
            entry = library.list_items()[0]
            library.delete(entry["id"])
            library.migrate_legacy(source, items)
            self.assertEqual(library.list_items(), [])
            self.assertTrue(Path(entry["path"]).is_file())

    def test_invalid_upload_does_not_create_catalog_entry(self):
        with tempfile.TemporaryDirectory() as workspace:
            library = TemplateLibrary(workspace)
            with self.assertRaises(FileNotFoundError):
                library.add({"name": "缺失模板", "path": "missing.xlsx"}, workspace)
            self.assertEqual(library.list_items(), [])

    def test_updates_from_other_product_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as workspace:
            template = self.template(workspace)
            first, second = TemplateLibrary(workspace), TemplateLibrary(workspace)
            item = first.add({"name": "A", "path": str(template)})
            second.add({"name": "B", "path": str(template)})
            first.update_metadata(item["id"], {"name": "新A"})
            self.assertEqual([item["name"] for item in second.list_items()], ["新A", "B"])


if __name__ == "__main__":
    unittest.main()
