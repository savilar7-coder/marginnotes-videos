import tempfile
import unittest
from pathlib import Path
from render_guard import validate_inputs, finish_encoder, RenderInputError

class RenderGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
    def asset(self, relative, data=b"fixture"):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p
    def timeline(self, shots=None):
        return {"dur": 2.0, "fps": 30, "shots": shots or [{"t0": 0, "t1": 2, "plate": "room"}]}
    def test_missing_art_stops_instead_of_gray_frame(self):
        with self.assertRaisesRegex(RenderInputError, "room.png"):
            validate_inputs(self.timeline(), self.root, 0, 2)
    def test_empty_art_is_not_ready(self):
        self.asset("plates/room.png", b"")
        with self.assertRaises(RenderInputError):
            validate_inputs(self.timeline(), self.root, 0, 2)
    def test_layered_shot_requires_both_background_and_figure(self):
        self.asset("plates/room.png")
        tl = self.timeline([{ "t0": 0, "t1": 2, "plate": "room", "fig": 1}])
        with self.assertRaisesRegex(RenderInputError, "room_bg.png"):
            validate_inputs(tl, self.root, 0, 2)
        self.asset("plates/room_bg.png")
        self.asset("layers/room.png")
        self.assertEqual(validate_inputs(tl, self.root, 0, 2)["required_assets"], 3)
    def test_flat_depth_is_allowed_for_a_still(self):
        self.asset("plates/room.png")
        self.assertEqual(validate_inputs(self.timeline(), self.root, 0, 2)["selected_shots"], 1)
    def test_range_test_does_not_need_unseen_later_art(self):
        self.asset("plates/room.png")
        tl = self.timeline([{ "t0": 0, "t1": 1, "plate": "room"}, {"t0": 1, "t1": 2, "plate": "later"}])
        validate_inputs(tl, self.root, 0, 1)
    def test_crossfade_checks_previous_shot_used_in_transition(self):
        self.asset("plates/room.png")
        tl = self.timeline([{ "t0": 0, "t1": 1, "plate": "earlier"}, {"t0": 1, "t1": 2, "plate": "room", "xfade": 0.3}])
        with self.assertRaisesRegex(RenderInputError, "earlier.png"):
            validate_inputs(tl, self.root, 1.1, 2)
    def test_bad_range_and_timeline_gap_stop(self):
        self.asset("plates/room.png")
        with self.assertRaises(RenderInputError):
            validate_inputs(self.timeline(), self.root, 2, 1)
        tl = self.timeline([{ "t0": 0, "t1": .5, "plate": "room"}, {"t0": 1, "t1": 2, "plate": "room"}])
        with self.assertRaisesRegex(RenderInputError, "Uncovered"):
            validate_inputs(tl, self.root, 0, 2)
    def test_missing_clip_stops(self):
        with self.assertRaisesRegex(RenderInputError, "acting.mp4"):
            validate_inputs(self.timeline([{ "t0": 0, "t1": 2, "clip": "acting.mp4"}]), self.root, 0, 2)
    def encoder(self, returncode):
        class Pipe:
            def close(self): pass
        class Encoder:
            stdin = Pipe()
            def wait(self): return returncode
        return Encoder()
    def test_encoder_failure_is_not_success_even_with_partial_file(self):
        out = self.asset("partial.mp4")
        with self.assertRaisesRegex(RuntimeError, "exit code 9"):
            finish_encoder(self.encoder(9), out)
    def test_encoder_success_requires_nonempty_output(self):
        out = self.root / "out.mp4"
        with self.assertRaisesRegex(RuntimeError, "nonempty"):
            finish_encoder(self.encoder(0), out)
        out.write_bytes(b"")
        with self.assertRaises(RuntimeError):
            finish_encoder(self.encoder(0), out)
        out.write_bytes(b"completed")
        finish_encoder(self.encoder(0), out)

if __name__ == "__main__":
    unittest.main()
