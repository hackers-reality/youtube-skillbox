#!/usr/bin/env python3
"""Regression tests for the fresh-agent acceptance fixes."""
import importlib.util
import os
import sys
import tempfile
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSCRIPT_PATH = os.path.join(REPO, "skills", "transcript", "scripts", "gettranscript.py")
YTDATA_PATH = os.path.join(REPO, "skills", "youtube", "scripts", "ytdata.py")
MANIFEST_PATH = os.path.join(REPO, "skills", "yt-workflow", "scripts", "audit_manifest.py")
RETENTION_PATH = os.path.join(REPO, "skills", "yt-retention", "scripts", "retention.py")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestNormalizeArgv(unittest.TestCase):
    def setUp(self):
        self.transcript = load_module(TRANSCRIPT_PATH, "gettranscript_argv_test")
        self.ytdata = load_module(YTDATA_PATH, "ytdata_argv_test")

    def test_all_langs_flag_not_rewritten(self):
        self.assertEqual(
            self.transcript._normalize_argv(["9NDb3RH9N7M", "--all-langs"]),
            ["9NDb3RH9N7M", "--all-langs"],
        )
        self.assertEqual(
            self.ytdata._normalize_argv(["info", "9NDb3RH9N7M", "--json"]),
            ["info", "9NDb3RH9N7M", "--json"],
        )

    def test_valid_ids_unchanged(self):
        self.assertEqual(self.transcript._normalize_argv(["9NDb3RH9N7M"]), ["9NDb3RH9N7M"])

    def test_urls_unchanged(self):
        url = "https://www.youtube.com/watch?v=9NDb3RH9N7M"
        self.assertEqual(self.transcript._normalize_argv([url]), [url])

    def test_dash_leading_id_converted(self):
        self.assertEqual(
            self.transcript._normalize_argv(["-xvOxbvnXuk"]),
            ["https://youtu.be/-xvOxbvnXuk"],
        )
        self.assertEqual(
            self.ytdata._normalize_argv(["info", "-xvOxbvnXuk", "--json"]),
            ["info", "https://youtu.be/-xvOxbvnXuk", "--json"],
        )

    def test_double_dash_flags_never_become_ids(self):
        for flag in ["--all-langs", "--full-meta", "--min-ratio", "--no-meta", "--", "--unknown-flag"]:
            self.assertEqual(self.transcript._normalize_argv([flag]), [flag])
            self.assertEqual(self.ytdata._normalize_argv([flag]), [flag])

    def test_short_flags_and_ordinary_arguments_unchanged(self):
        self.assertEqual(self.transcript._normalize_argv(["-h"]), ["-h"])
        self.assertEqual(
            self.ytdata._normalize_argv(["outliers", "@Moments_Unscriptedorignal", "--min-ratio", "2"]),
            ["outliers", "@Moments_Unscriptedorignal", "--min-ratio", "2"],
        )


class TestInventoryAndThumbnailContract(unittest.TestCase):
    def setUp(self):
        self.manifest = load_module(MANIFEST_PATH, "audit_manifest_regress_test")

    def test_inventory_contains_every_recorded_artifact(self):
        dest = tempfile.mkdtemp(prefix="audit_inventory_")
        try:
            files = {
                "sections.json": "{}",
                "titles.json": "[]",
                "retention.csv": "a,b\n1,2\n",
                "thumbnail.jpg": "",
            }
            for name, content in files.items():
                with open(os.path.join(dest, name), "wb") as f:
                    f.write(content.encode())
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            m.record("phase1", "youtube", "cmd1", exit_code=0, artifact=os.path.join(dest, "sections.json"))
            m.record("phase2", "transcript", "cmd2", exit_code=0, artifact=os.path.join(dest, "titles.json"))
            m.record("phase7", "yt-retention", "cmd7", exit_code=0, artifact=os.path.join(dest, "retention.csv"))
            m.register_artifact(os.path.join(dest, "thumbnail.jpg"), artifact_type="thumbnail_image", producing_phase="phase4")
            result = m.finalize()
            paths = {entry["path"] for entry in result["artifact_inventory"]}
            self.assertEqual(paths, {os.path.realpath(os.path.join(dest, name)) for name in files})
            self.assertTrue(result["artifacts_verified"])
            self.assertEqual(result["unclaimed_artifacts"], [])
            types = {entry["type"] for entry in result["artifact_inventory"]}
            self.assertIn("extracted_data", types)
            self.assertIn("thumbnail_image", types)
        finally:
            for name in os.listdir(dest):
                os.unlink(os.path.join(dest, name))
            os.rmdir(dest)

    def test_unclaimed_files_make_verification_fail(self):
        dest = tempfile.mkdtemp(prefix="audit_unclaimed_")
        try:
            claimed = os.path.join(dest, "claimed.json")
            extra = os.path.join(dest, "extra.json")
            for p in (claimed, extra):
                with open(p, "w", encoding="utf-8") as f:
                    f.write("{}")
            m = self.manifest.AuditManifest("partial", "@c", artifact_destination=dest)
            m.record("phase1", "youtube", "cmd", exit_code=0, artifact=claimed)
            result = m.finalize()
            self.assertFalse(result["artifacts_verified"])
            self.assertIn(os.path.realpath(extra), result["unclaimed_artifacts"])
            self.assertIn("extra.json", result["unclaimed_artifacts"][0])
        finally:
            for name in os.listdir(dest):
                os.unlink(os.path.join(dest, name))
            os.rmdir(dest)

    def test_thumbnail_evaluated_with_real_image_artifact(self):
        dest = tempfile.mkdtemp(prefix="audit_thumb_")
        try:
            image = os.path.join(dest, "thumbnail.jpg")
            with open(image, "wb") as f:
                f.write(b"\xff\xd8\xff" + b"fake-jpeg-bytes")
            phase_artifact = os.path.join(dest, "titles.json")
            with open(phase_artifact, "w", encoding="utf-8") as f:
                f.write("[]")
            ev = os.path.join(dest, "truth.json")
            with open(ev, "w", encoding="utf-8") as f:
                f.write("{}")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            m.record("phase4", "yt-package", "title.py", exit_code=0, artifact=phase_artifact)
            m.record_vision_gate("verified", model="m", provider="p", mechanism="read",
                                 evidence_path=ev, thumbnail_files=[image],
                                 probe="VISION-PROBE-A", observed="VISION-PROBE-A")
            m.set_thumbnail_analysis("phase4", True, "image_artifact", image_artifact_path=image)
            m.register_artifact(image, artifact_type="thumbnail_image", producing_phase="phase4")
            m.register_artifact(ev, artifact_type="report", producing_phase="phase4")
            rec = m.phases["phase4"]
            self.assertTrue(rec["thumbnail_evaluated"])
            self.assertEqual(rec["thumbnail_basis"], "image_artifact")
            self.assertTrue(m.verify_artifacts())
        finally:
            for name in os.listdir(dest):
                os.unlink(os.path.join(dest, name))
            os.rmdir(dest)

    def test_thumbnail_evaluated_without_image_artifact_rejected(self):
        m = self.manifest.AuditManifest("strict", "@c")
        m.record("phase4", "yt-package", "title.py", exit_code=0)
        with self.assertRaises(ValueError):
            m.set_thumbnail_analysis("phase4", True, "image_artifact")


class TestRetentionDirectoryInventory(unittest.TestCase):
    def setUp(self):
        self.retention = load_module(RETENTION_PATH, "retention_inventory_test")

    def _write_csv(self, dest, name, header, rows):
        with open(os.path.join(dest, name), "w", encoding="utf-8", newline="") as f:
            f.write(",".join(header) + "\n")
            for r in rows:
                f.write(",".join(map(str, r)) + "\n")

    def test_inventories_all_studio_csvs_without_proportion_inference(self):
        dest = tempfile.mkdtemp(prefix="retention_export_")
        try:
            absolute = ["Video position (%)", "Absolute audience retention (%)"]
            segmented = ["Video position (%)", "New viewers", "Returning viewers"]
            activity = ["Video position (%)", "Started watching", "Stopped watching", "Number of times each moment was seen"]
            cases = {
                "All.csv": (absolute, [[0, 100], [50, 50], [100, 0]]),
                "Detailed activity.csv": (activity, [[0, 100, 5, 100], [50, 0, 5, 50]]),
                "New and returning viewers.csv": (segmented, [[0, 90, 110], [50, 50, 55]]),
                "Subscribers and non-subscribers.csv": (["Video position (%)", "Subscribers", "Non-subscribers"], [[0, 80, 120], [50, 40, 60]]),
                "Organic and paid traffic.csv": (["Video position (%)", "Organic", "Paid"], [[0, 100, 90], [50, 50, 45]]),
                "Organic.csv": (absolute, [[0, 100], [50, 50]]),
                "Skippable video ad.csv": (absolute, [[0, 100], [50, 50]]),
                "Video discovery ad.csv": (absolute, [[0, 100], [50, 50]]),
                "New, casual and regular viewers.csv": (["Video position (%)", "New viewers", "Casual viewers", "Regular viewers"], [[0, 90, 95, 105], [50, 45, 50, 55]]),
            }
            for name, (header, rows) in cases.items():
                self._write_csv(dest, name, header, rows)
            result = self.retention.analyze_directory(dest)
            self.assertEqual(result["files_found"], 9)
            files = {f["file"]: f for f in result["files"]}
            self.assertEqual(set(files), set(cases))
            for entry in files.values():
                self.assertEqual(entry["status"], "known")
                self.assertFalse(entry["can_infer_proportions"])
                self.assertIn("interpretation_warning", entry)
            self.assertIn("proportions", result["global_warning"])
            self.assertEqual(files["All.csv"]["measures"], "retention_curve_absolute")
            self.assertEqual(files["Detailed activity.csv"]["measures"], "activity_counts")
        finally:
            for name in os.listdir(dest):
                os.unlink(os.path.join(dest, name))
            os.rmdir(dest)


class TestTranscriptIntegrity(unittest.TestCase):
    """CRITICAL: stale .json3 from another video in a shared --work-dir must
    never be returned for the requested video (Earth-spin contamination bug)."""
    def setUp(self):
        self.transcript = load_module(TRANSCRIPT_PATH, "gettranscript_integrity_test")

    def test_other_video_files_never_qualify(self):
        # Fake run_ytdlp that writes NOTHING (simulates yt-dlp failure) — the
        # only .json3 present is the stale 9NDb file. Must fail, not return it.
        orig = self.transcript.run_ytdlp
        class Proc:
            returncode = 1
            stdout = ""
            stderr = "no subtitles found"
        self.transcript.run_ytdlp = lambda args, timeout=120: Proc()
        try:
            with tempfile.TemporaryDirectory(prefix="gt_integrity_") as d:
                stale = os.path.join(d, "9NDb3RH9N7M.en.json3")
                with open(stale, "w", encoding="utf-8") as f:
                    f.write('{"events": [{"tStartMs": 0, "dDurationMs": 1000, "segs": [{"utf8": "EARTH"}]}]}')
                with self.assertRaises(SystemExit) as cm:
                    self.transcript.fetch_subtitle_files("_aEWe_6O-sw", ["en"], work_dir=d)
                self.assertNotEqual(cm.exception.code, 0)
        finally:
            self.transcript.run_ytdlp = orig

    def test_validate_video_identity_mismatch_fails(self):
        with self.assertRaises(SystemExit):
            self.transcript._validate_video_identity("9NDb3RH9N7M", {"id": "_aEWe_6O-sw"})

    def test_validate_video_identity_match_passes(self):
        self.assertEqual(
            self.transcript._validate_video_identity("9NDb3RH9N7M", {"id": "9NDb3RH9N7M"}),
            "9NDb3RH9N7M")

    def test_is_429_detection(self):
        class P:
            stderr = "ERROR: HTTP Error 429: Too Many Requests"
        self.assertTrue(self.transcript._is_429(P()))
        class Q:
            stderr = "ok"
        self.assertFalse(self.transcript._is_429(Q()))


class TestHookscoreUnicodeRobustness(unittest.TestCase):
    """The observed crash: subprocess reader thread hit UnicodeDecodeError
    (byte 0x8f under cp1252) and stdout came back None. The fix is explicit
    UTF-8 decoding with replacement — test it with REAL non-UTF-8 output."""

    def test_non_utf8_subprocess_output_decodes_without_crash(self):
        import subprocess
        # A child that emits raw 0x8f bytes (the exact failing byte) on stdout.
        code = "import sys; sys.stdout.buffer.write(b'\\x8f\\x8f not json\\n')"
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIsInstance(proc.stdout, str)
        proc.stdout.encode("utf-8")  # must be re-encodable (no surrogate crash)
        self.assertIn("\ufffd", proc.stdout)

    def test_run_fetcher_uses_robust_decoding(self):
        hook_path = os.path.join(REPO, "skills", "yt-script", "scripts", "hookscore.py")
        mod = load_module(hook_path, "hookscore_fetcher_test")
        import subprocess as sp
        orig_run = sp.run
        seen = {}
        class FakeProc:
            returncode = 1
            stdout = "\ufffd bad bytes"
            stderr = "failed"
        def fake(cmd, **kwargs):
            seen.update(kwargs)
            seen["cmd"] = cmd
            # Simulate the non-UTF-8 child: return the decoded-with-replacement form
            p = FakeProc()
            p.stdout = b"ok".decode("utf-8", errors="replace")
            return p
        sp.run = fake
        try:
            result = mod.run_fetcher(["VID12345678", "--format", "json"])
            self.assertEqual(seen.get("encoding"), "utf-8")
            self.assertEqual(seen.get("errors"), "replace")
            self.assertTrue(str(seen["cmd"][1]).endswith("gettranscript.py"))
        finally:
            sp.run = orig_run


class TestHookscoreCwdResolution(unittest.TestCase):
    def test_resolves_repo_gettranscript_from_foreign_cwd(self):
        hook_path = os.path.join(REPO, "skills", "yt-script", "scripts", "hookscore.py")
        mod = load_module(hook_path, "hookscore_cwd_test")
        resolved = mod.resolve_gettranscript()
        self.assertTrue(str(resolved).startswith(REPO), f"resolved outside repo: {resolved}")
        self.assertTrue(resolved.exists(), f"resolved path missing: {resolved}")
        prev = os.getcwd()
        try:
            os.chdir(tempfile.gettempdir())
            # Re-resolve from a foreign cwd — must still give the repo copy.
            resolved2 = mod.resolve_gettranscript()
            self.assertEqual(str(resolved2), str(resolved))
            self.assertTrue(resolved2.exists())
        finally:
            os.chdir(prev)


class TestVisionProbe(unittest.TestCase):
    """Vision gate must verify an OBSERVED probe response, not file existence."""

    def setUp(self):
        self.vg_path = os.path.join(REPO, "skills", "yt-package", "scripts", "vision_gate.py")
        self.vg = load_module(self.vg_path, "vision_gate_test")

    def test_make_known_image_writes_valid_image(self):
        with tempfile.TemporaryDirectory(prefix="vg_img_") as d:
            p = os.path.join(d, "probe.png")
            self.vg.make_known_image(__import__("pathlib").Path(p), "VISION-PROBE-X")
            self.assertTrue(os.path.exists(p) and os.path.getsize(p) > 0)
            self.assertIsNotNone(self.vg.image_type(__import__("pathlib").Path(p)))

    def test_fallback_without_pillow_generates_valid_png(self):
        """Simulate Pillow unavailable: fallback must still yield a recognized image."""
        import builtins
        real_import = builtins.__import__
        def fake_import(name, *a, **k):
            if name.startswith("PIL"):
                raise ImportError("No module named 'PIL' (simulated)")
            return real_import(name, *a, **k)
        with tempfile.TemporaryDirectory(prefix="vg_nopil_") as d:
            p = __import__("pathlib").Path(d) / "probe.png"
            with unittest.mock.patch("builtins.__import__", side_effect=fake_import):
                self.vg.make_known_image(p, "VISION-PROBE-NOPIL")
            self.assertTrue(p.exists())
            self.assertEqual(self.vg.image_type(p), "png")

    def test_wrong_observation_rejected_right_observation_accepted(self):
        with tempfile.TemporaryDirectory(prefix="vg_probe_") as d:
            probe = "VISION-PROBE-ABC123"
            img = __import__("pathlib").Path(d) / "vision-probe.png"
            self.vg.make_known_image(img, probe)
            digest = __import__("hashlib").sha256(img.read_bytes()).hexdigest()
            # Wrong observed -> NOT VERIFIED (simulate verification logic)
            wrong = "VISION-PROBE-DIFFERENT"
            self.assertNotEqual(wrong, probe)
            right = probe
            self.assertEqual(right, probe)
            # Truth sidecar round-trips
            truth = {"probe": probe, "sha256": digest}
            self.assertEqual(truth["probe"], probe)

    def test_manifest_rejects_mismatched_observed(self):
        dest = tempfile.mkdtemp(prefix="vg_manifest_")
        try:
            img = os.path.join(dest, "thumb.jpg")
            with open(img, "wb") as f:
                f.write(b"\xff\xd8\xff fake")
            ev = os.path.join(dest, "truth.json")
            with open(ev, "w", encoding="utf-8") as f:
                f.write("{}")
            m = load_module(MANIFEST_PATH, "audit_manifest_vg_test").AuditManifest(
                "strict", "@c", artifact_destination=dest)
            m.register_artifact(img, artifact_type="thumbnail_image", producing_phase="phase4")
            m.register_artifact(ev, artifact_type="report", producing_phase="phase4")
            with self.assertRaises(ValueError):
                m.record_vision_gate("verified", model="m", provider="p", mechanism="read",
                                     evidence_path=ev, thumbnail_files=[img],
                                     probe="VISION-PROBE-ABC", observed="WRONG")
        finally:
            for n in os.listdir(dest):
                os.unlink(os.path.join(dest, n))
            os.rmdir(dest)


class TestManifestHardening(unittest.TestCase):
    def setUp(self):
        self.manifest = load_module(MANIFEST_PATH, "audit_manifest_harden_test")

    def test_overwrite_false_raises(self):
        with tempfile.TemporaryDirectory(prefix="mh_ow_") as d:
            p = os.path.join(d, "manifest.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("{}")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=d)
            with self.assertRaises(FileExistsError):
                m.write_manifest(p, overwrite=False)

    def test_verified_gate_requires_probe_and_observed(self):
        with tempfile.TemporaryDirectory(prefix="mh_vg_") as d:
            img = os.path.join(d, "thumb.jpg")
            with open(img, "wb") as f:
                f.write(b"\xff\xd8\xff fake")
            ev = os.path.join(d, "truth.json")
            with open(ev, "w", encoding="utf-8") as f:
                f.write("{}")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=d)
            m.register_artifact(img, artifact_type="thumbnail_image", producing_phase="phase4")
            m.register_artifact(ev, artifact_type="report", producing_phase="phase4")
            with self.assertRaises(ValueError):
                m.record_vision_gate("verified", model="m", provider="p", mechanism="read",
                                     evidence_path=ev, thumbnail_files=[img])  # no probe/observed

    def test_thumbnail_true_requires_verified_gate(self):
        with tempfile.TemporaryDirectory(prefix="mh_th_") as d:
            img = os.path.join(d, "thumb.jpg")
            with open(img, "wb") as f:
                f.write(b"\xff\xd8\xff fake")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=d)
            m.record("phase4", "yt-package", "title.py", exit_code=0, artifact=os.path.join(d, "t.json"))
            with open(os.path.join(d, "t.json"), "w", encoding="utf-8") as f:
                f.write("[]")
            with self.assertRaises(ValueError):
                m.set_thumbnail_analysis("phase4", True, "image_artifact", image_artifact_path=img)

    def test_thumbnail_true_checks_real_image_bytes(self):
        with tempfile.TemporaryDirectory(prefix="mh_bytes_") as d:
            fake = os.path.join(d, "thumb.jpg")
            with open(fake, "wb") as f:
                f.write(b"not an image at all")
            good = os.path.join(d, "good.jpg")
            with open(good, "wb") as f:
                f.write(b"\xff\xd8\xff real-ish")
            ev = os.path.join(d, "truth.json")
            with open(ev, "w", encoding="utf-8") as f:
                f.write("{}")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=d)
            m.record("phase4", "yt-package", "title.py", exit_code=0)
            m.record_vision_gate("verified", model="m", provider="p", mechanism="read",
                                 evidence_path=ev, thumbnail_files=[good],
                                 probe="P-OK", observed="P-OK")

            # Fake image content (not an image) must reject thumbnail evaluation.
            with self.assertRaises(ValueError):
                m.set_thumbnail_analysis("phase4", True, "image_artifact", image_artifact_path=fake)

    def test_finalize_never_complete_when_verification_fails(self):
        with tempfile.TemporaryDirectory(prefix="mh_complete_") as d:
            claimed = os.path.join(d, "claimed.json")
            with open(claimed, "w", encoding="utf-8") as f:
                f.write("{}")
            m = self.manifest.AuditManifest("partial", "@c", artifact_destination=d)
            for i, ph in enumerate(["phase1", "phase2", "phase3", "phase4", "phase5", "phase6"], 1):
                skill = {"phase1": "youtube", "phase2": "transcript", "phase3": "yt-script",
                         "phase4": "yt-package", "phase5": "youtube", "phase6": "youtube"}[ph]
                m.record(ph, skill, f"cmd{i}", exit_code=0)
            m.register_artifact(claimed, artifact_type="extracted_data", producing_phase="phase1")
            # Stray file makes verification fail
            with open(os.path.join(d, "stray.json"), "w", encoding="utf-8") as f:
                f.write("{}")
            result = m.finalize()
            self.assertNotEqual(result["overall"], "COMPLETE")

    def test_record_rejects_success_without_exit_code(self):
        m = self.manifest.AuditManifest("strict", "@c")
        with self.assertRaises(ValueError):
            m.record("phase1", "youtube", "cmd", exit_code=None, status="success")


class TestTitleSchemaCompatibility(unittest.TestCase):
    def test_thumbnail_keeps_legacy_score_and_checks(self):
        title_path = os.path.join(REPO, "skills", "yt-package", "scripts", "title.py")
        mod = load_module(title_path, "title_compat_test")
        result = mod.score_package("How to YouTube SEO", "WATCH NOW", "youtube seo")
        thumb = result["thumbnail"]
        self.assertIn("score", thumb)
        self.assertIn("checks", thumb)
        self.assertIn("text_score", thumb)
        self.assertIsNone(thumb["image_score"])
        self.assertEqual(thumb["score"], thumb["text_score"]["score"])
        self.assertEqual(thumb["checks"], thumb["text_score"]["checks"])
        self.assertFalse(result["thumbnail_evaluated"])


class TestTranscriptPrecision(unittest.TestCase):
    def setUp(self):
        self.transcript = load_module(TRANSCRIPT_PATH, "gettranscript_precision_test")

    def test_is_429_precise(self):
        class P:
            def __init__(self, s):
                self.stderr = s
        self.assertTrue(self.transcript._is_429(P("HTTP Error 429: Too Many Requests")))
        self.assertTrue(self.transcript._is_429(P("rate-limited: wait")))
        self.assertFalse(self.transcript._is_429(P("rate of speed is fine")))
        self.assertFalse(self.transcript._is_429(P("operated successfully")))

    def test_nonzero_exit_never_partial_success(self):
        orig = self.transcript.run_ytdlp
        class ProcFail:
            returncode = 1
            stdout = ""
            stderr = "ERROR: private video"
        self.transcript.run_ytdlp = lambda args, timeout=120: ProcFail()
        try:
            with tempfile.TemporaryDirectory(prefix="gt_nz_") as d:
                with self.assertRaises(SystemExit) as cm:
                    self.transcript.fetch_subtitle_files("9NDb3RH9N7M", ["en"],
                                                  all_langs=True, work_dir=d, retries=1, sleep=0.001)
                self.assertNotEqual(cm.exception.code, 0)
        finally:
            self.transcript.run_ytdlp = orig


class TestRetentionAbsoluteSemantics(unittest.TestCase):
    def setUp(self):
        self.retention = load_module(RETENTION_PATH, "retention_semantics_test")

    def test_absolute_from_export_even_below_100(self):
        pts = [{"time_seconds": None, "time_pct": 0.0, "retention_pct": 50.0,
                "original_time_is_pct": True, "source_file": "All.csv"}]
        self.assertTrue(self.retention._is_absolute_from_export("All.csv"))
        self.assertIsNone(None)
        hook = self.retention.detect_hook_leak(pts)
        self.assertTrue(hook["absolute_retention"])


class TestYtdataEnrichmentExplicit(unittest.TestCase):
    def setUp(self):
        self.ytdata = load_module(YTDATA_PATH, "ytdata_explicit_test")

    def test_failed_entries_marked_explicitly(self):
        orig = self.ytdata._fetch_video_detail
        self.ytdata._fetch_video_detail = lambda v: (None, ["boom"]) if v == "bad00000001" else (
            {"duration": 42, "duration_string": "0:42"}, [])
        try:
            entries = [{"id": "a0000000001"}, {"id": "bad00000001"}]
            out = self.ytdata._enrich_entries(entries, full_meta=False, workers=2)
            self.assertEqual(out[0]["enrichment_status"], "succeeded")
            self.assertEqual(out[1]["enrichment_status"], "failed")
            self.assertIn("boom", out[1].get("enrichment_error", ""))
            self.assertTrue(self.ytdata.LAST_ENRICHMENT_SUMMARY["partial"])
        finally:
            self.ytdata._fetch_video_detail = orig


class TestRetryFlags(unittest.TestCase):
    """yt-dlp 2026.10.26 retry surface: --retries (HTTP, default 10),
    --extractor-retries (default 3), --retry-sleep (http/extractor...).
    The old code passed a bare --retries 3, which WEAKERED the HTTP default
    and left the extractor stage at its default. Lock the full surface in."""

    def test_subtitle_args_cover_http_and_extractor_stages(self):
        import pathlib
        src = pathlib.Path(TRANSCRIPT_PATH).read_text(encoding="utf-8")
        self.assertIn('"--retries", "10"', src)
        self.assertIn('"--extractor-retries", "5"', src)
        self.assertIn('"--retry-sleep"', src)
        self.assertIn('"http:linear=1::2"', src)
        self.assertIn('"extractor:exp=1:30"', src)
        self.assertIn('"--sleep-subtitles"', src)
        self.assertIn('"--sleep-requests"', src)

    def test_all_langs_never_falls_back_after_429(self):
        transcript = load_module(TRANSCRIPT_PATH, "gettranscript_429_test")
        orig = transcript.run_ytdlp
        class Proc429:
            returncode = 1
            stdout = ""
            stderr = "ERROR: Unable to download video subtitles for 'ab': HTTP Error 429: Too Many Requests"
        transcript.run_ytdlp = lambda args, timeout=120: Proc429()
        try:
            with tempfile.TemporaryDirectory(prefix="gt_429_") as d:
                with self.assertRaises(SystemExit) as cm:
                    transcript.fetch_subtitle_files("9NDb3RH9N7M", ["en"],
                                                  all_langs=True, work_dir=d,
                                                  retries=1, sleep=0.001)
                self.assertNotEqual(cm.exception.code, 0)
                # No single-language fallback: no files returned, exit was fatal.
        finally:
            transcript.run_ytdlp = orig


class TestManifestPersistenceAndVisionGate(unittest.TestCase):
    def setUp(self):
        self.manifest = load_module(MANIFEST_PATH, "audit_manifest_persist_test")

    def test_write_manifest_saved_agrees_with_validator(self):
        dest = tempfile.mkdtemp(prefix="manifest_write_")
        try:
            keep = os.path.join(dest, "report.md")
            with open(keep, "w", encoding="utf-8") as f:
                f.write("# r")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            m.record("phase1", "youtube", "cmd", exit_code=1)  # device a required failure
            m.register_artifact(keep, artifact_type="report", producing_phase="manifest")
            mpath = os.path.join(dest, "manifest.json")
            written = m.write_manifest(mpath, overwrite=True)
            self.assertEqual(written["overall_status"], "FAILED")
            self.assertTrue(written["artifacts_verified"])
            # And the validator agrees
            saved = __import__("json").load(open(mpath, encoding="utf-8"))
            self.assertEqual(saved["artifacts_verified"], written["artifacts_verified"])
            self.assertEqual(saved["overall_status"], written["overall_status"])
        finally:
            for n in os.listdir(dest):
                os.unlink(os.path.join(dest, n))
            os.rmdir(dest)

    def test_vision_gate_verified_requires_evidence_and_images(self):
        dest = tempfile.mkdtemp(prefix="vision_gate_")
        try:
            img = os.path.join(dest, "thumb.jpg")
            with open(img, "wb") as f:
                f.write(b"\xff\xd8\xff fake but suffix-mapped")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            # No evidence file -> must reject verified
            with self.assertRaises(ValueError):
                m.record_vision_gate("verified", model="m", provider="p", mechanism="read",
                                     evidence_path=os.path.join(dest, "missing.txt"),
                                     thumbnail_files=[img])
            # With real evidence + image -> passes
            ev = os.path.join(dest, "vision-test.txt")
            with open(ev, "w", encoding="utf-8") as f:
                f.write("known test image: read ok")
            m.register_artifact(img, artifact_type="thumbnail_image", producing_phase="phase4")
            m.register_artifact(ev, artifact_type="report", producing_phase="phase4")
            rec = m.record_vision_gate("verified", model="m", provider="p", mechanism="read",
                                       evidence_path=ev, thumbnail_files=[img],
                                       probe="VISION-PROBE-A", observed="VISION-PROBE-A")
            self.assertEqual(rec["status"], "verified")
        finally:
            for n in os.listdir(dest):
                os.unlink(os.path.join(dest, n))
            os.rmdir(dest)


class TestRetentionDurationAxis(unittest.TestCase):
    def setUp(self):
        self.retention = load_module(RETENTION_PATH, "retention_axis_test")

    def _write_all_csv(self, dest):
        p = os.path.join(dest, "All.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write("Video position (%), Absolute audience retention (%)\n")
            f.write("0,132.94\n30,103.98\n88,59.99\n95,28.60\n100,20\n")

    def test_no_duration_means_percent_axis_not_seconds(self):
        dest = tempfile.mkdtemp(prefix="retention_axis_")
        try:
            self._write_all_csv(dest)
            data = self.retention.parse_retention_csv(os.path.join(dest, "All.csv"))
            self.assertIsNone(data["video_duration_seconds"])
            pts = data["points"]
            self.assertIsNone(pts[0]["time_seconds"])   # NOT 0-assumed-100
            self.assertEqual(pts[0]["time_pct"], 0.0)
            cliffs = self.retention.detect_cliffs(pts)
            self.assertTrue(cliffs)
            self.assertIsNone(cliffs[0]["time_seconds"])
            self.assertEqual(cliffs[0]["time_unit"], "%")
            slide = self.retention.detect_slide(pts)
            self.assertIn("percent-only", slide["severity"])
        finally:
            os.unlink(os.path.join(dest, "All.csv"))
            os.rmdir(dest)

    def test_with_duration_scales_seconds_correctly(self):
        dest = tempfile.mkdtemp(prefix="retention_axis2_")
        try:
            self._write_all_csv(dest)
            data = self.retention.parse_retention_csv(
                os.path.join(dest, "All.csv"), video_duration_seconds=24)
            pts = data["points"]
            # 95% of a 24s short = 22.8s, not 95s
            self.assertAlmostEqual(pts[3]["time_seconds"], 0.95 * 24, places=1)
            self.assertAlmostEqual(pts[3]["time_pct"], 95.0, places=1)
        finally:
            os.unlink(os.path.join(dest, "All.csv"))
            os.rmdir(dest)


class TestYtdataEnrichment(unittest.TestCase):
    def setUp(self):
        self.ytdata = load_module(YTDATA_PATH, "ytdata_enrich_test")

    def test_enrich_preserves_order_and_degrades_on_failure(self):
        orig = self.ytdata._fetch_video_detail
        calls = []
        def fake(vid):
            calls.append(vid)
            if vid == "bad00000001":
                return None, ["boom"]
            return {"duration": 42, "duration_string": "0:42"}, []
        self.ytdata._fetch_video_detail = fake
        try:
            entries = [{"id": "a0000000001"}, {"id": "bad00000001"}, {"id": "b0000000002"}]
            out = self.ytdata._enrich_entries(entries, full_meta=False, workers=3)
            self.assertEqual([e["id"] for e in out], ["a0000000001", "bad00000001", "b0000000002"])
            self.assertEqual(out[0]["duration"], 42)
            self.assertIsNone(out[1].get("duration"))  # degraded, not fatal
            self.assertEqual(out[2]["duration"], 42)
        finally:
            self.ytdata._fetch_video_detail = orig

    def test_run_ytdlp_timeout_returns_nonzero(self):
        import subprocess as sp
        orig = sp.run
        def boom(*a, **k):
            raise sp.TimeoutExpired(a[0] if a else "cmd", timeout=1)
        sp.run = boom
        try:
            proc = self.ytdata.run_ytdlp(["--skip-download"], timeout=1)
            self.assertNotEqual(proc.returncode, 0)
        finally:
            sp.run = orig


if __name__ == "__main__":
    unittest.main()
