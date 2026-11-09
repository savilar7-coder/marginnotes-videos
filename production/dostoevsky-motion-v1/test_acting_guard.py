import copy
import unittest
from render_guard import validate_acting, RenderInputError

class ActingGuardTests(unittest.TestCase):
    def setUp(self):
        self.shot = {"t0": 10, "t1": 15.8, "fig": 1, "acting": {
            "kind": "seated_lean", "interval": [1, 2.6], "angle_degrees": -2.5,
            "pivot": [1100, 840], "seat_blend": [640, 900]}}
    def test_valid_shot_local_times(self):
        validate_acting(self.shot, "shot")
    def test_unknown_kind_cannot_silently_fall_back_to_sway(self):
        self.shot["acting"]["kind"] = "seated_typo"
        with self.assertRaisesRegex(RenderInputError, "unknown acting"):
            validate_acting(self.shot, "shot")
    def test_zero_negative_and_outside_intervals_stop(self):
        for interval in ([1, 1], [2, 1], [-1, 2], [1, 8]):
            with self.subTest(interval=interval):
                self.shot["acting"]["interval"] = interval
                with self.assertRaisesRegex(RenderInputError, "acting interval"):
                    validate_acting(self.shot, "shot")
    def test_zero_blend_or_nonfinite_geometry_stops(self):
        for key, value in (("seat_blend", [640, 640]), ("pivot", [float("nan"), 840]), ("angle_degrees", float("inf"))):
            with self.subTest(key=key):
                shot = copy.deepcopy(self.shot)
                shot["acting"][key] = value
                with self.assertRaises(RenderInputError):
                    validate_acting(shot, "shot")
    def test_action_requires_layers_and_cannot_be_ignored_on_clip(self):
        self.shot["fig"] = 0
        with self.assertRaisesRegex(RenderInputError, "layered figure"):
            validate_acting(self.shot, "shot")
        self.shot["fig"] = 1
        self.shot["clip"] = "scene.mp4"
        with self.assertRaisesRegex(RenderInputError, "layered figure"):
            validate_acting(self.shot, "shot")

if __name__ == "__main__":
    unittest.main()
