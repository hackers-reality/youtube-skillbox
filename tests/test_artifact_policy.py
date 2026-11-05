#!/usr/bin/env python3
"""
Regression tests for the Artifact Destination Policy and Subagent availability rule.

Policy (owned by yt-guide, inherited by yt-workflow & creator skills):
- Destination must be absolute; missing/uncreatable -> ValueError (no silent fallback)
- Artifacts outside the destination are rejected (absolute or `..` substitution)
- Existing files are never overwritten without explicit permission
- Everything verified inside the destination; artifact list reported
"""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(REPO, "skills", "yt-workflow", "scripts", "audit_manifest.py")
YT_GUIDE_SKILL = os.path.join(REPO, "skills", "yt-guide", "SKILL.md")
YT_WORKFLOW_SKILL = os.path.join(REPO, "skills", "yt-workflow", "SKILL.md")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestDestinationEnforcement(unittest.TestCase):
    def setUp(self):
        self.manifest = load_module(MANIFEST_PATH, "audit_manifest_dest_test")

    def test_destination_must_be_absolute(self):
        with self.assertRaises(ValueError):
            self.manifest.AuditManifest("strict", "@c", artifact_destination="relative\\dir")

    def test_destination_as_file_is_rejected(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x")
            path = f.name
        try:
            with self.assertRaises(ValueError):
                self.manifest.AuditManifest("strict", "@c", artifact_destination=path)
        finally:
            os.unlink(path)

    def test_destination_created_if_missing(self):
        dest = os.path.join(tempfile.gettempdir(), "audit_dest_test_xyz_123")
        if os.path.exists(dest):
            shutil.rmtree(dest, ignore_errors=True)
        try:
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            self.assertEqual(m.artifact_destination, os.path.realpath(dest))
            self.assertTrue(os.path.isdir(dest))
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_relative_artifact_rejected_when_destination_set(self):
        dest = tempfile.mkdtemp(prefix="audit_dest_")
        try:
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            with self.assertRaises(ValueError):
                m.record("phase1", "youtube", "ytdata sections", exit_code=0, artifact="sections.json")
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_dotdot_escape_rejected(self):
        dest = tempfile.mkdtemp(prefix="audit_dest_")
        try:
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            evil = os.path.join(dest, "..", "evil.json")
            with self.assertRaises(ValueError):
                m.record("phase1", "youtube", "ytdata sections", exit_code=0, artifact=evil)
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_absolute_outside_destination_rejected(self):
        dest = tempfile.mkdtemp(prefix="audit_dest_")
        other = tempfile.mkdtemp(prefix="audit_other_")
        try:
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            for ep in (os.path.join(other, "evil.json"), os.path.join(other, "sub", "evil.json")):
                with self.assertRaises(ValueError):
                    m.record("phase1", "youtube", "x", exit_code=0, artifact=ep)
        finally:
            shutil.rmtree(dest, ignore_errors=True)
            shutil.rmtree(other, ignore_errors=True)

    def test_absolute_inside_destination_accepted(self):
        dest = tempfile.mkdtemp(prefix="audit_dest_")
        try:
            p = os.path.join(dest, "sections.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("{}")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            m.record("phase1", "youtube", "ytdata sections", exit_code=0, artifact=p)
            result = m.finalize()
            self.assertIn(p, result["artifact_list"])
            self.assertTrue(result["artifacts_verified"])
            self.assertEqual(result["artifact_destination"], os.path.realpath(dest))
            self.assertEqual(result["artifact_policy"], "user_selected")
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_subdir_inside_destination_accepted(self):
        dest = tempfile.mkdtemp(prefix="audit_dest_")
        sub = os.path.join(dest, "phase1", "raw")
        os.makedirs(sub)
        try:
            p = os.path.join(sub, "sections.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("{}")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            m.record("phase1", "youtube", "ytdata sections", exit_code=0, artifact=p)
            self.assertTrue(m.finalize()["artifacts_verified"])
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_missing_artifact_blocks_verification(self):
        dest = tempfile.mkdtemp(prefix="audit_dest_")
        try:
            p = os.path.join(dest, "missing.json")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            m.record("phase1", "youtube", "ytdata sections", exit_code=0, artifact=p)
            self.assertFalse(m.finalize()["artifacts_verified"])
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_overwrite_refused_without_permission(self):
        dest = tempfile.mkdtemp(prefix="audit_dest_")
        try:
            p = os.path.join(dest, "manifest.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("{}")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            with self.assertRaises(FileExistsError):
                m.ensure_artifact_path(p)
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_overwrite_allowed_with_permission(self):
        dest = tempfile.mkdtemp(prefix="audit_dest_")
        try:
            p = os.path.join(dest, "manifest.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("{}")
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            self.assertEqual(m.ensure_artifact_path(p, overwrite=True), os.path.realpath(p))
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_artifact_outside_destination_via_ensure_rejected(self):
        dest = tempfile.mkdtemp(prefix="audit_dest_")
        outside = tempfile.mkdtemp(prefix="audit_outside_")
        try:
            m = self.manifest.AuditManifest("strict", "@c", artifact_destination=dest)
            with self.assertRaises(ValueError):
                m.ensure_artifact_path(os.path.join(outside, "x.json"), overwrite=True)
        finally:
            shutil.rmtree(dest, ignore_errors=True)
            shutil.rmtree(outside, ignore_errors=True)

    def test_artifacts_verified_when_destination_not_set_is_false(self):
        m = self.manifest.AuditManifest("strict", "@c")
        self.assertFalse(m.finalize()["artifacts_verified"])


class TestSubagentAvailabilityContract(unittest.TestCase):
    def _read(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_yt_guide_has_subagent_availability_rule(self):
        text = self._read(YT_GUIDE_SKILL)
        self.assertIn("Subagents are optional", text)
        self.assertIn("Never invent a delegation tool", text)
        self.assertIn("HTTP 429", text)

    def test_yt_workflow_inherits_destination_and_subagent_rules(self):
        text = self._read(YT_WORKFLOW_SKILL)
        self.assertIn("Artifact Destination Policy", text)
        self.assertIn("Subagents only if the harness exposes them", text)

    def test_no_temp_default_instructions_in_workflow(self):
        text = self._read(YT_WORKFLOW_SKILL)
        self.assertNotIn("temp working dir", text)
        self.assertNotIn("temp files, pass paths forward", text)


if __name__ == "__main__":
    unittest.main()
