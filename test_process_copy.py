import unittest

from core.bubble_engine import BubbleEngine, BubbleError


class ProcessCopyTests(unittest.TestCase):
    def test_matches_sequence_preserves_position_and_undoes_batch(self):
        engine = BubbleEngine([dict(seq=1, x=10, y=20, req='old'),
                               dict(seq=1.1, x=30, y=40), dict(seq=3, x=50, y=60)])
        before = [dict(b) for b in engine.bubbles]
        count = engine.copy_contents_from([dict(seq=1, x=999, y=999, req='new'),
                                           dict(seq=1.1, x=999, y=999, req='child'),
                                           dict(seq=2, x=0, y=0)])
        self.assertEqual(count, 2)
        self.assertEqual([(b['x'], b['y']) for b in engine.bubbles], [(10, 20), (30, 40), (50, 60)])
        self.assertEqual(engine.get(1.1)['req'], 'child')
        self.assertEqual(engine.get(3), before[2])
        self.assertTrue(engine.undo())
        self.assertEqual(engine.bubbles, before)

    def test_process_copy_creates_missing_children_at_target_parent_and_copies_gauges(self):
        engine = BubbleEngine([dict(seq=2, x=11, y=12, req="old")])
        source = [dict(seq=2, x=99, y=98, req="new", gauges=[{"name": "Ring gauge", "spec": "10 mm", "part_no": "G-1"}]),
                  dict(seq=2.1, x=1, y=1, req="child")]
        self.assertEqual(engine.copy_contents_from(source), 2)
        self.assertEqual([b["seq"] for b in engine.sorted()], [2, 2.1])
        self.assertEqual((engine.get(2)["x"], engine.get(2)["y"]), (11, 12))
        self.assertEqual((engine.get(2.1)["x"], engine.get(2.1)["y"]), (35, 36))
        self.assertEqual(engine.get(2.1)['req'], 'child')
        self.assertEqual(engine.get(2)["gauges"][0]["part_no"], "G-1")
        self.assertTrue(engine.undo())
        self.assertIsNone(engine.get(2.1))
        self.assertEqual(engine.get(2)['req'], 'old')

    def test_copy_child_without_any_target_group_uses_source_position(self):
        engine = BubbleEngine()
        self.assertEqual(engine.copy_contents_from([dict(seq=4.1, x=73, y=81, req='child')]), 1)
        self.assertEqual((engine.get(4.1)['x'], engine.get(4.1)['y']), (73, 81))
        self.assertEqual(engine.next_sequence(), 5)

    def test_child_creation_near_parent_and_coordinate_edits_undo(self):
        engine = BubbleEngine([dict(seq=2, x=10, y=20)])
        child = engine.add_child(2)
        self.assertEqual((child['x'], child['y']), (34, 44))
        engine.update(2.1, {'x': 60})
        self.assertEqual([(b['x'], b['y']) for b in engine.bubbles], [(10, 20), (60, 44)])
        engine.undo()
        self.assertEqual([(b['x'], b['y']) for b in engine.bubbles], [(10, 20), (34, 44)])

    def test_hidden_children_are_not_hit_targets_and_copy_is_bounded(self):
        engine = BubbleEngine([dict(seq=2, x=95, y=95)])
        engine.copy_contents_from([dict(seq=2.1, x=0, y=0)], bounds=(100, 100))
        self.assertEqual((engine.get(2.1)['x'], engine.get(2.1)['y']), (99, 99))
        self.assertEqual(engine.hit_test(95, 95, 18)['seq'], 2)
        self.assertEqual(len(engine.visible_bubbles()), 1)

    def test_invalid_source_is_atomic_and_no_match_has_no_history(self):
        engine = BubbleEngine([dict(seq=1, x=10, y=20)])
        self.assertEqual(engine.copy_contents_from([dict(seq=2, x=0, y=0)]), 0)
        self.assertEqual(engine.history_size, 0)
        with self.assertRaises(BubbleError):
            engine.copy_contents_from([dict(seq=1, x=0, y=0), dict(seq=1, x=0, y=0)])
        self.assertEqual(engine.history_size, 0)
