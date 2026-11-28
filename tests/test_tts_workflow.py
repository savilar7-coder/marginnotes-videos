"""Offline regression checks for the Python actually embedded in tts-manual.yml.

HTTP and ffprobe are mocked. No live account, provider, Git, or network calls.
"""
import base64
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
from unittest import mock
import urllib.error

WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github/workflows/tts-manual.yml"
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")
start = WORKFLOW.index("          python3 - <<'PY'\n") + len("          python3 - <<'PY'\n")
end = WORKFLOW.index("          PY\n", start)
CODE = compile(textwrap.dedent(WORKFLOW[start:end]), "tts-manual.yml:inline-python", "exec")


class NarrationGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tts-offline-")
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "scripts/selected.txt").write_text("Hello world.", encoding="utf-8")
        (self.root / "scripts/other.txt").write_text("Must never be synthesized.", encoding="utf-8")
        self.env = {"TTS_APPROVED": "true", "TTS_SCRIPT": "selected.txt", "TTS_MAX_CHARACTERS": "100",
                    "XI_KEY": "offline-test-key", "GITHUB_OUTPUT": str(self.root / "step-output.txt")}
        self.requests = []
        self.provider_error = None
        self.provider_audio = b"VALID-MP3-TEST-FIXTURE"
        self.ffprobe_available = True

    def tearDown(self):
        self.temp.cleanup()

    def fake_http(self, request, timeout):
        self.requests.append(request)
        if self.provider_error:
            raise self.provider_error
        return io.BytesIO(json.dumps({"audio_base64": base64.b64encode(self.provider_audio).decode(),
                                     "alignment": {"characters": ["H"], "character_start_times_seconds": [0]}}).encode())

    def fake_probe(self, command, **kwargs):
        self.assertEqual(command[0], "ffprobe")
        valid = Path(command[-1]).read_bytes().startswith(b"VALID-MP3")
        info = {"streams": [{"codec_name": "mp3"}], "format": {"duration": "0.5"}}
        return subprocess.CompletedProcess(command, 0 if valid else 1, json.dumps(info), "")

    def run_workflow_python(self):
        previous = Path.cwd()
        output = io.StringIO()
        try:
            os.chdir(self.root)
            with mock.patch.dict(os.environ, self.env, clear=True), \
                 mock.patch("urllib.request.urlopen", side_effect=self.fake_http), \
                 mock.patch("subprocess.run", side_effect=self.fake_probe), \
                 mock.patch("shutil.which", return_value="ffprobe" if self.ffprobe_available else None), \
                 redirect_stdout(output):
                exec(CODE, {"__name__": "__main__"})
        finally:
            os.chdir(previous)
        return output.getvalue()

    def assert_denied_without_request(self):
        with self.assertRaises(SystemExit):
            self.run_workflow_python()
        self.assertEqual(self.requests, [])
        self.assertFalse((self.root / "audio/selected.mp3").exists())

    def test_unapproved_and_nonpositive_or_invalid_ceiling_never_call(self):
        for approved, ceiling in (("false", "100"), ("", "100"), ("yes", "100"),
                                  ("true", "0"), ("true", "-1"), ("true", "1.5"), ("true", "")):
            with self.subTest(approved=approved, ceiling=ceiling):
                self.env.update(TTS_APPROVED=approved, TTS_MAX_CHARACTERS=ceiling)
                self.assert_denied_without_request()

    def test_over_limit_never_calls(self):
        self.env["TTS_MAX_CHARACTERS"] = "11"
        self.assert_denied_without_request()

    def test_one_selected_script_and_headers_preserved(self):
        source = '#voice: customVoice123\n#model: eleven_v3\n#settings: {"stability": 0.0, "speed": 1.1}\nHello'
        (self.root / "scripts/selected.txt").write_text(source, encoding="utf-8")
        self.env["TTS_MAX_CHARACTERS"] = "5"
        self.run_workflow_python()
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertIn("/customVoice123/with-timestamps?output_format=mp3_44100_128", request.full_url)
        body = json.loads(request.data)
        self.assertEqual(body, {"text": "Hello", "model_id": "eleven_v3", "voice_settings": {
            "stability": 0.0, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True, "speed": 1.1}})
        self.assertEqual(sorted(p.name for p in (self.root / "audio").iterdir()), ["selected.json", "selected.mp3"])
        self.assertEqual((self.root / "step-output.txt").read_text(), "generated=true\nname=selected\n")

    def test_defaults_preserved(self):
        self.run_workflow_python()
        self.assertIn("/onwK4e9ZLuTAKqWW03F9/", self.requests[0].full_url)
        body = json.loads(self.requests[0].data)
        self.assertEqual(body["model_id"], "eleven_v3")
        self.assertEqual(body["text"], "Hello world.")

    def test_present_valid_audio_skips_even_without_api_key(self):
        (self.root / "audio").mkdir()
        path = self.root / "audio/selected.mp3"
        path.write_bytes(b"VALID-MP3-EXISTING")
        self.env.pop("XI_KEY")
        self.assertIn("skipped existing valid audio", self.run_workflow_python())
        self.assertEqual(self.requests, [])
        self.assertEqual(path.read_bytes(), b"VALID-MP3-EXISTING")
        self.assertFalse((self.root / "step-output.txt").exists())

    def test_invalid_existing_audio_fails_closed(self):
        (self.root / "audio").mkdir()
        path = self.root / "audio/selected.mp3"
        path.write_bytes(b"BROKEN")
        with self.assertRaises(SystemExit):
            self.run_workflow_python()
        self.assertEqual(self.requests, [])
        self.assertEqual(path.read_bytes(), b"BROKEN")

    def test_orphan_alignment_fails_closed(self):
        (self.root / "audio").mkdir()
        (self.root / "audio/selected.json").write_text("{}")
        self.assert_denied_without_request()

    def test_header_errors_empty_and_invalid_identifiers_never_call(self):
        for text in ('#settings: [1,2]\nHello', '#settings: {broken}\nHello',
                     '#settings: {"stability": NaN}\nHello', '#voice: ../bad\nHello',
                     '#model: model?injected=true\nHello', '#voice:\nHello', '#model: eleven_v3\n'):
            with self.subTest(text=text):
                (self.root / "scripts/selected.txt").write_text(text, encoding="utf-8")
                self.assert_denied_without_request()

    def test_paths_wildcards_and_traversal_never_call(self):
        for name in ("../selected.txt", "scripts/selected.txt", "..\\selected.txt", "*.txt", "a.txt\nb.txt", "/tmp/a.txt", "a.txt;echo.txt"):
            with self.subTest(name=name):
                self.env["TTS_SCRIPT"] = name
                self.assert_denied_without_request()

    def test_symlink_source_directory_and_output_guards(self):
        for target_name in ("scripts", "selected.txt", "audio", "selected.mp3", "selected.json"):
            with self.subTest(target_name=target_name), mock.patch.object(Path, "is_symlink", lambda path: path.name == target_name):
                self.assert_denied_without_request()

    def test_missing_validator_never_calls(self):
        self.ffprobe_available = False
        self.assert_denied_without_request()

    def test_http_error_is_not_retried(self):
        self.provider_error = urllib.error.HTTPError("https://api.elevenlabs.io", 429, "offline", {}, None)
        with self.assertRaisesRegex(SystemExit, "HTTP 429"):
            self.run_workflow_python()
        self.assertEqual(len(self.requests), 1)
        self.assertFalse((self.root / "audio/selected.mp3").exists())

    def test_failed_provider_audio_is_not_committed_or_retried(self):
        self.provider_audio = b"BROKEN"
        with self.assertRaisesRegex(SystemExit, "failed validation"):
            self.run_workflow_python()
        self.assertEqual(len(self.requests), 1)
        self.assertFalse((self.root / "audio/selected.mp3").exists())
        self.assertFalse((self.root / "step-output.txt").exists())

    def test_only_manual_guard_is_maintained(self):
        self.assertFalse(WORKFLOW_PATH.with_name("tts.yml").exists())
        self.assertTrue(WORKFLOW.startswith("name: Narration (manual approval only)\n"))

    def test_workflow_is_manual_serialized_and_commits_only_named_outputs(self):
        self.assertNotIn("\n  push:", WORKFLOW)
        self.assertIn("\n  workflow_dispatch:", WORKFLOW)
        self.assertIn("cancel-in-progress: false", WORKFLOW)
        self.assertLess(WORKFLOW.index('git checkout --detach FETCH_HEAD'), WORKFLOW.index('id: synthesize'))
        self.assertIn('git add -- "audio/$AUDIO_NAME.mp3" "audio/$AUDIO_NAME.json"', WORKFLOW)
        self.assertNotIn("glob(", WORKFLOW)
        self.assertNotIn("git add audio", WORKFLOW)


if __name__ == "__main__":
    unittest.main(verbosity=2)
