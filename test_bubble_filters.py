import unittest
from unittest.mock import Mock

from core.bubble_filters import matches, value_counts
from ui.bubble_app import BubbleApp


class ColumnFilterTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"seq": 1, "item": "外径", "tool": "卡尺", "req": "10±1"},
            {"seq": 2, "item": "外径", "tool": "千分尺", "req": "20±1"},
            {"seq": 3, "item": "长度", "tool": "卡尺", "req": "30"},
            {"seq": 4, "item": "", "tool": "卡尺", "req": ""},
        ]

    def test_multiple_keywords_any_and_all(self):
        filters = {"item": {"query": "外径，长度"}}
        self.assertEqual([r["seq"] for r in self.rows if matches(r, filters)], [1, 2, 3])
        filters = {"req": {"query": "10;±1", "mode": "all"}}
        self.assertEqual([r["seq"] for r in self.rows if matches(r, filters)], [1])

    def test_exact_multiselect_combines_with_keywords_and_other_columns(self):
        filters = {"item": {"values": ["外径", "长度"], "query": "径"},
                   "tool": {"values": ["卡尺"]}}
        self.assertEqual([r["seq"] for r in self.rows if matches(r, filters)], [1])
        self.assertTrue(matches(self.rows[3], {"item": {"values": [""]}}))
        self.assertFalse(matches(self.rows[0], {"item": {"values": [""]}}))

    def test_counts_ignore_current_column_but_honor_other_columns(self):
        filters = {"item": {"values": ["长度"]}, "tool": {"values": ["卡尺"]}}
        self.assertEqual(value_counts(self.rows, "item", filters), {"外径": 1, "长度": 1, "": 1})
        self.assertEqual(value_counts(self.rows, "item", {}), {"外径": 2, "长度": 1, "": 1})

    def test_navigation_uses_visible_rows_and_keeps_column_for_space(self):
        app = BubbleApp.__new__(BubbleApp)
        app.tree = Mock()
        app.tree.get_children.return_value = ("1", "3")
        app.tree.selection.return_value = ("1",)
        app.tree.column.return_value = 100
        app.tree.xview.return_value = (0, 0.5)
        app.active_column = "#2"
        app.column_filters = {}
        app.status = Mock()
        app._redraw = Mock()
        app._open_cell_editor = Mock()
        self.assertEqual(app._navigate_cell(Mock(keysym="Right")), "break")
        self.assertEqual(app.active_column, "#3")
        app._edit_cell_keyboard()
        app._open_cell_editor.assert_called_once_with("1", "#3")
        app._navigate_cell(Mock(keysym="Down"))
        app.tree.selection_set.assert_called_with("3")
        app._navigate_cell(Mock(keysym="Up"))
        app.tree.selection_set.assert_called_with("1")
