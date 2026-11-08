"""Exercise gesture recognition without a camera or macOS input events."""

import unittest

from gestures import Gestures
from settings import Settings, validate_settings


def hand(*extended: int, pinch: bool = False, x: float = 0.5, y: float = 0.5) -> list:
    points = [(x, y + 0.2, 0.0)] * 21
    points[9] = (x, y, 0.0)
    for tip in extended:
        points[tip - 2] = (x, y, 0.0)
        points[tip] = (x, y - 0.2, 0.0)
    if pinch:
        points[4] = points[8]
    return points


class GestureTests(unittest.TestCase):
    def setUp(self):
        self.gestures = Gestures()

    def update(self, points, time):
        return self.gestures.update(points, time, 1.0)

    def hold(self, points, start, ticks):
        for tick in range(ticks + 1):
            result = self.update(points, start + tick / 10)
        return result

    def test_index_moves_and_two_fingers_do_not_move_pointer(self):
        self.assertIsNotNone(self.update(hand(8), 0).position)
        self.assertIsNone(self.update(hand(8, 12), 0.1).position)

    def test_dwell_click_fires_once(self):
        self.assertEqual(self.hold(hand(8), 0, 14).button, "")
        self.assertEqual(self.update(hand(8), 1.5).button, "click")
        self.assertEqual(self.update(hand(8), 1.6).button, "")

    def test_peace_hold_right_clicks_once(self):
        self.assertEqual(self.hold(hand(8, 12), 0, 8).button, "right")
        self.assertEqual(self.update(hand(8, 12), 0.9).button, "up")

    def test_moving_peace_sign_scrolls_without_right_clicking(self):
        self.update(hand(8, 12), 0)
        self.assertGreater(self.update(hand(8, 12, y=0.44), 0.2).scroll, 0)
        self.assertNotEqual(self.hold(hand(8, 12, y=0.44), 0.3, 6).button, "right")

    def test_pinch_grab_drop_and_tracking_loss(self):
        point, pinch = hand(8), hand(pinch=True)
        self.update(point, 0)
        self.update(pinch, 0.05)
        self.assertEqual(self.update(point, 0.15).button, "down")
        self.assertIsNotNone(self.update(point, 0.2).position)
        self.update(pinch, 0.25)
        self.assertEqual(self.update(point, 0.35).button, "up")
        self.update(pinch, 0.4)
        self.assertEqual(self.update(point, 0.5).button, "down")
        self.assertEqual(self.update(None, 0.6).button, "up")

    def test_fist_and_palm_pause_and_resume_without_shortcut(self):
        paused = self.hold(hand(), 0, 10)
        self.assertTrue(self.gestures.paused)
        self.assertFalse(paused.shortcut)
        resumed = self.hold(hand(8, 12, 16, 20), 1.2, 11)
        self.assertFalse(self.gestures.paused)
        self.assertFalse(resumed.shortcut)

    def test_palm_then_fist_minimises(self):
        self.hold(hand(8, 12, 16, 20), 0, 2)
        self.assertEqual(self.hold(hand(), 0.3, 2).shortcut, "minimize")

    def test_fist_then_palm_toggles_fullscreen(self):
        self.hold(hand(), 0, 2)
        self.assertEqual(self.hold(hand(8, 12, 16, 20), 0.3, 2).shortcut, "fullscreen")

    def test_precision_starts_at_current_cursor(self):
        self.gestures = Gestures(Settings(smoothing_ms=0), precision_origin=(0.4, 0.4))
        self.assertEqual(self.update(hand(8), 0).position, (0.4, 0.4))
        x, _ = self.update(hand(8, x=0.6), 0.1).position
        self.assertTrue(0.4 < x < 0.48)

    def test_settings_reject_inverted_calibration(self):
        with self.assertRaises(ValueError):
            validate_settings({"calibrated_area": [0.8, 0.2, 0.2, 0.8]})


if __name__ == "__main__":
    unittest.main()
