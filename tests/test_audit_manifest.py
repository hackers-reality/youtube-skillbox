#!/usr/bin/env python3
"""
Regression tests for the yt-workflow audit contract:
- strict vs partial mode behavior
- execution manifest (failed phase can never be marked success)
- thumbnail honesty (text-only basis can never claim visual evaluation)
- differentiation of keyword opportunity vs competition scores
- heuristic scores are never presented as CTR/ranking predictions
- report claims carry MEASURED/INFERRED/HYPOTHESIS evidence labels
"""
import importlib.util
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(REPO, "skills", "yt-workflow", "scripts", "audit_manifest.py")
TITLE_PATH = os.path.join(REPO, "skills", "yt-package", "scripts", "title.py")
YTDATA_PATH = os.path.join(REPO, "skills", "youtube", "scripts", "ytdata.py")
YT_WORKFLOW_SKILL = os.path.join(REPO, "skills", "yt-workflow", "SKILL.md")
YT_PACKAGE_SKILL = os.path.join(REPO, "skills", "yt-package", "SKILL.md")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestAuditManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = load_module(MANIFEST_PATH, "audit_manifest_test")

    def test_strict_stops_on_required_failure(self):
        m = self.manifest.AuditManifest("strict", "@chan")
        m.record("phase1", "youtube", "ytdata sections", exit_code=0)
        m.record("phase2", "transcript", "gettranscript ...", exit_code=429)
        result = m.finalize()
        self.assertEqual(result["overall"], "FAILED")
        self.assertEqual(result["stopped_at_phase"], "phase2")

    def test_partial_continues_and_labels(self):
        m = self.manifest.AuditManifest("partial", "@chan")
        m.record("phase1", "youtube", "ytdata sections", exit_code=0)
        m.record("phase2", "transcript", "gettranscript ...", exit_code=429)
        m.record("phase3", "yt-script", "hookscore.py t.json", exit_code=0)
        result = m.finalize()
        self.assertEqual(result["overall"], "PARTIAL")
        self.assertIsNone(result["stopped_at_phase"])
        self.assertIn(("phase2", "failed"), result["required_failures"])

    def test_all_pass_strict_complete(self):
        m = self.manifest.AuditManifest("strict", "@chan")
        for ph in ["phase1", "phase2", "phase3", "phase4", "phase5", "phase6"]:
            m.record(ph, self.manifest.PHASE_SKILLS[ph], f"cmd {ph}", exit_code=0)
        self.assertEqual(m.finalize()["overall"], "COMPLETE")

    def test_failed_phase_marked_success_rejected(self):
        m = self.manifest.AuditManifest("strict", "@chan")
        with self.assertRaises(ValueError):
            m.record("phase2", "transcript", "gettranscript ...", exit_code=1, status="success")

    def test_failed_phase_cannot_be_marked_success_later(self):
        m = self.manifest.AuditManifest("strict", "@chan")
        m.record("phase2", "transcript", "gettranscript ...", exit_code=1)
        rec = m.phases["phase2"]
        self.assertEqual(rec["status"], "failed")

    def test_thumbnail_text_only_cannot_claim_visual_eval(self):
        m = self.manifest.AuditManifest("strict", "@chan")
        m.record("phase4", "yt-package", "title.py --file t.json", exit_code=0)
        with self.assertRaises(ValueError):
            m.set_thumbnail_analysis("phase4", True, "user_supplied_text")

    def test_thumbnail_text_only_label(self):
        m = self.manifest.AuditManifest("strict", "@chan")
        m.record("phase4", "yt-package", "title.py --file t.json", exit_code=0)
        m.set_thumbnail_analysis("phase4", False, "user_supplied_text")
        self.assertFalse(m.phases["phase4"]["thumbnail_evaluated"])

    def test_heuristic_note_present(self):
        m = self.manifest.AuditManifest("strict", "@chan")
        for ph in ["phase1", "phase2", "phase3", "phase4", "phase5", "phase6"]:
            m.record(ph, self.manifest.PHASE_SKILLS[ph], f"cmd {ph}", exit_code=0)
        note = m.finalize()["heuristic_note"]
        self.assertIn("not predictions", note.lower())

    def test_evidence_labels_validated(self):
        m = self.manifest.AuditManifest("strict", "@chan")
        m.add_claim("131 subs measured", "MEASURED")
        with self.assertRaises(ValueError):
            m.add_claim("CTR will improve", "PROMISE")


class TestScorePackageHonesty(unittest.TestCase):
    def setUp(self):
        self.title = load_module(TITLE_PATH, "title_pkg_audit_test")

    def test_thumbnail_not_evaluated_when_no_text(self):
        result = self.title.score_package("Test Title", thumb_text="")
        self.assertFalse(result["thumbnail_evaluated"])
        self.assertEqual(result["thumbnail_basis"], "none")
        self.assertIn("NOT evaluated", result["thumbnail_note"])

    def test_thumbnail_text_only_labeled_user_supplied(self):
        result = self.title.score_package("Test Title", thumb_text="WATCH THIS", keyword="test")
        self.assertTrue(result["thumbnail_evaluated"])
        self.assertEqual(result["thumbnail_basis"], "user_supplied_text")
        self.assertIn("NOT a visual evaluation", result["thumbnail_note"])

    def test_heuristic_note_disclaims_prediction(self):
        result = self.title.score_package("Test Title", thumb_text="")
        self.assertIn("heuristic", result["heuristic_note"].lower())
        self.assertIn("not predictions", result["heuristic_note"].lower())


class TestSkillContractFiles(unittest.TestCase):
    """The agent reads SKILL.md — the contract must live there, not just in code."""

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_yt_workflow_mentions_guide_consult(self):
        text = self._read(YT_WORKFLOW_SKILL)
        self.assertIn("yt-guide", text)
        self.assertIn("CONSULT yt-guide", text)

    def test_yt_workflow_has_both_modes(self):
        text = self._read(YT_WORKFLOW_SKILL)
        self.assertIn("strict", text.lower())
        self.assertIn("partial", text.lower())
        self.assertIn("OVERALL: FAILED", text)
        self.assertIn("PARTIAL AUDIT", text)

    def test_yt_workflow_requires_manifest(self):
        text = self._read(YT_WORKFLOW_SKILL)
        self.assertIn("manifest.json", text)
        self.assertIn("audit_manifest.py", text)

    def test_yt_workflow_keywords_vs_competition_distinguished(self):
        text = self._read(YT_WORKFLOW_SKILL)
        self.assertIn("opportunity_score", text)
        self.assertIn("competition_score", text)

    def test_yt_workflow_evidence_labels(self):
        text = self._read(YT_WORKFLOW_SKILL)
        for label in ("MEASURED", "INFERRED", "HYPOTHESIS"):
            self.assertIn(label, text)

    def test_yt_workflow_thumbnail_honesty(self):
        text = self._read(YT_WORKFLOW_SKILL)
        self.assertIn("thumbnail_evaluated", text)
        self.assertIn("user-supplied TEXT", text)

    def test_yt_workflow_heuristic_not_prediction(self):
        text = self._read(YT_WORKFLOW_SKILL)
        self.assertIn("heuristic", text.lower())
        self.assertIn("predictions", text.lower())

    def test_yt_package_forbids_fabricated_visual_claims(self):
        text = self._read(YT_PACKAGE_SKILL)
        self.assertIn("Honesty rules", text)
        self.assertIn("text only", text)
        self.assertIn("not evaluated", text)

    def test_yt_package_verification_verdict_counts(self):
        text = self._read(YT_PACKAGE_SKILL)
        self.assertIn("Verdicts must match the tool", text)


class TestScoreAliasesPresent(unittest.TestCase):
    """ytdata must emit BOTH opportunity_score and competition_score so agents
    cannot confuse them."""

    def test_both_score_aliases_exist(self):
        with open(YTDATA_PATH, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("opportunity_score", src)
        self.assertIn("competition_score", src)


if __name__ == "__main__":
    unittest.main()
