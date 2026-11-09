import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from core.bubble_engine import BubbleEngine, sequence_label
from ui.bubble_app import BubbleApp


class BubbleEditingTests(unittest.TestCase):
    def test_drag_saves_one_undo_operation(self):
        app = BubbleApp.__new__(BubbleApp)
        app.drawing = {"id": "d"}
        app.engines = {"d": BubbleEngine([{"seq": 1, "x": 20, "y": 30}])}
        app.display = (10, 10, 200, 200, 0.5)
        app.image_size = (400, 400)
        app.drag_start = ("1", (20, 30), (20, 30))
        app.canvas = Mock()
        app._redraw = Mock()
        app._changed = Mock()
        app._on_canvas_drag(Mock(x=60, y=70))
        app._on_canvas_drag(Mock(x=70, y=80))
        self.assertEqual(app.engine.history_size, 0)
        app._on_canvas_release(Mock())
        self.assertEqual((app.engine.get(1)["x"], app.engine.get(1)["y"]), (120, 140))
        self.assertEqual(app.engine.history_size, 1)
        app.engine.undo()
        self.assertEqual(app.engine.get(1)["x"], 20)

    def test_edit_filter_drag_and_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            try:
                root = tk.Tk()
            except tk.TclError as exc:
                self.skipTest(f"Tk unavailable: {exc}")
            try:
                app = BubbleApp(root, folder)
                product = app.repository.create("编辑测试")
                image = app.workspace / "drawing.png"
                cv2.imencode(".png", np.zeros((200, 300, 3), dtype=np.uint8))[1].tofile(image)
                app.repository.add_drawing(product, image)
                app._refresh_products(product["id"])
                root.update()
                bubble = app.engine.add(30, 40)
                app.selected_seq = sequence_label(bubble["seq"])
                app._changed()
                root.update()
                app.tree.selection_set("1")
                app.active_column = "#1"
                app._edit_cell_keyboard()
                root.update()
                editor = root.focus_get()
                editor.delete(0, tk.END)
                editor.insert(0, "2")
                editor.event_generate("<Return>")
                root.update()
                self.assertIsNotNone(app.engine.get(2))
                self.assertIsNone(app.engine.get(1))
                app.column_filters["item"] = {"query": "absent"}
                app._refresh_table()
                self.assertEqual(app.tree.get_children(), ())
                app._clear_filters()
                self.assertEqual(app.tree.get_children(), ("2",))
                app.drag_start = ("2", (30, 40), (30, 40))
                ox, oy, _, _, scale = app.display
                app._on_canvas_drag(Mock(x=ox + 80 * scale, y=oy + 90 * scale))
                app._on_canvas_release(Mock())
                self.assertEqual((app.engine.get(2)["x"], app.engine.get(2)["y"]), (80, 90))
                loaded = app.repository.load(product["id"])
                self.assertEqual(loaded["drawings"][0]["bubbles"][0]["x"], 80)
                app.undo()
                self.assertEqual(app.engine.get(2)["x"], 30)
            finally:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
