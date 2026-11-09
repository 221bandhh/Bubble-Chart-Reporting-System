import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.bubble_engine import BubbleEngine
from data.product_repository import ProductRepository
from data.gauge_library import GaugeLibrary
from report_system.ui.app import ReportGeneratorApp
from ui.bubble_app import BubbleApp


class RequestedFeaturesTests(unittest.TestCase):
    def test_product_template_copies_are_isolated_and_reuse_own_edits(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            source = root / 'shared.xlsx'
            source.write_bytes(b'shared template')
            profiles = []
            for product in ('A', 'B'):
                app = ReportGeneratorApp.__new__(ReportGeneratorApp)
                app.config_file = str(root / product / 'report_generator_config.json')
                profile = app._own_template_profile('../unsafe:name', {
                    'path': str(source), 'sheet_config': {'report': {'header': 5}}})
                owned = Path(profile['path'])
                self.assertEqual(owned.parent, root / product / 'templates')
                self.assertEqual(owned.read_bytes(), b'shared template')
                profiles.append(profile)
                owned.write_bytes(product.encode())
                again = app._own_template_profile('../unsafe:name', profile)
                self.assertEqual(again['path'], profile['path'])
                self.assertEqual(owned.read_bytes(), product.encode())
            self.assertNotEqual(profiles[0]['path'], profiles[1]['path'])
            self.assertEqual(source.read_bytes(), b'shared template')
            source.unlink()
            self.assertEqual(Path(profiles[0]['path']).read_bytes(), b'A')
            self.assertEqual(Path(profiles[1]['path']).read_bytes(), b'B')

    def test_shared_gauge_history_keeps_variants_and_searches_all_fields(self):
        with tempfile.TemporaryDirectory() as workspace:
            first, other_product = GaugeLibrary(workspace), GaugeLibrary(workspace)
            first.remember([dict(name='Caliper', spec='0-100', part_no='A'),
                            dict(name='Caliper', spec='0-200', part_no='B')])
            other_product.remember([dict(name='Caliper', spec='0-100', part_no='A')])
            self.assertEqual(len(other_product.list_items()), 2)
            self.assertEqual(other_product.search('caliper 0-200')[0]['part_no'], 'B')
            self.assertEqual(other_product.search('A')[0]['spec'], '0-100')

    def test_folder_import_continues_after_invalid_product_and_keeps_sources(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as source:
            root = Path(source)
            for name in ('first', 'last'):
                folder = root / name
                folder.mkdir()
                (folder / 'drawing.png').write_bytes(b'image')
                (folder / 'product.json').write_text(json.dumps({
                    'name': name, 'image_path': 'drawing.png',
                    'bubbles': [dict(seq=1.1, x=7, y=8, req='10 +/- 1')]
                }), encoding='utf-8')
            bad = root / 'bad'
            bad.mkdir()
            (bad / 'project.json').write_text('{invalid', encoding='utf-8')
            repository = ProductRepository(workspace)
            imported, errors = repository.import_product_folders(root)
            self.assertEqual(len(imported), 2)
            self.assertEqual(len(errors), 1)
            self.assertEqual(len(repository.list_products()), 2)
            self.assertTrue((root / 'first' / 'drawing.png').is_file())
            for product in imported:
                loaded = repository.load(product['id'])
                self.assertEqual(loaded['drawings'][0]['bubbles'][0]['seq'], 1.1)

    def gauge_app(self):
        app = BubbleApp.__new__(BubbleApp)
        app.drawing = {'id': 'd', 'name': 'process', 'bubbles': []}
        app.product = {'drawings': [app.drawing]}
        app.engines = {'d': BubbleEngine([dict(seq=1.1, x=5, y=6, item='diameter', req='10 +/- 1',
            gauges=[dict(name='caliper', spec='0-100', part_no='A'),
                    dict(name='micrometer', spec='0-25', part_no='B')])])}
        app.repository = Mock()
        app.gauge_library = Mock()
        app._changed = Mock()
        return app

    def test_edit_one_gauge_preserves_siblings_and_requirement_edits_dimension(self):
        app = self.gauge_app()
        app._save_gauge_cell('d|1.1|1', 'spec', '0-50')
        bubble = app.engine.get(1.1)
        self.assertEqual(bubble['gauges'][0]['spec'], '0-100')
        self.assertEqual(bubble['gauges'][1]['spec'], '0-50')
        app._save_gauge_cell('d|1.1|0', 'req', '12 +/- 1')
        self.assertEqual(app.engine.get(1.1)['req'], '12 +/- 1')
        self.assertEqual(app.engine.get(1.1)['internal'], '12 +/- 1')
        self.assertEqual(app.engine.history_size, 2)

    def test_gauge_filters_include_requirement_and_retain_unfiltered_counts(self):
        app = self.gauge_app()
        app.gauge_tree = Mock()
        app.gauge_tree.get_children.return_value = ()
        app.gauge_selector = {}
        app.gauge_dimension_selector = {}
        app.gauge_dimension = Mock()
        app.gauge_dimension.get.return_value = ''
        app.gauge_drawing = Mock()
        app.gauge_drawing.get.return_value = '全部工序'
        app.gauge_filters = {'name': {'query': 'micro'}, 'req': {'query': '10'}}
        app._refresh_gauges()
        self.assertEqual(len(app._gauge_rows), 2)
        app.gauge_tree.insert.assert_called_once()
        values = app.gauge_tree.insert.call_args.kwargs['values']
        self.assertEqual(values[3], '10 +/- 1')
        self.assertEqual(values[4], 'micrometer')

    def test_right_click_deletes_only_chosen_child_and_can_undo(self):
        app = self.gauge_app()
        app.engine.add_child(1.1)
        app.tree = Mock()
        app.tree.identify_row.return_value = '1.2'
        menu = Mock()
        with patch('ui.bubble_app.tk.Menu', return_value=menu), \
             patch('ui.bubble_app.messagebox.askyesno', return_value=True):
            app.root = Mock()
            app._on_tree_right_click(Mock(y=1, x_root=2, y_root=3))
            menu.add_command.call_args.kwargs['command']()
        self.assertIsNone(app.engine.get(1.2))
        self.assertIsNotNone(app.engine.get(1.1))
        app.engine.undo()
        self.assertIsNotNone(app.engine.get(1.2))

    def test_canvas_renders_integer_group_once_but_keeps_child_rows(self):
        app = self.gauge_app()
        app.engine.add_child(1.1)
        app.photo = Mock()
        app.canvas = Mock()
        app.display = (0, 0, 100, 100, 1)
        app.selected_seq = '1.2'
        app._redraw()
        app.canvas.create_oval.assert_called_once()
        app.canvas.create_text.assert_called_once()
        self.assertEqual(app.canvas.create_text.call_args.kwargs['text'], '1')
        self.assertEqual(app.canvas.create_oval.call_args.kwargs['fill'], '#d32f2f')
        self.assertEqual([b['seq'] for b in app.engine.sorted()], [1.1, 1.2])


if __name__ == '__main__':
    unittest.main()
