#!/usr/bin/env python3
"""
YouTube Skillbox — audit manifest builder & validator.

An "audit manifest" is the machine-readable record an agent produces while
running yt-workflow. It exists to make agents HONEST:

- Every phase records which skill ran, which command ran, the exit code and
  where its output lives.
- A failed required phase can never flip to "success".
- Strict mode: first required-phase failure stops the audit; overall = FAILED.
- Partial mode: independent phases continue, overall = PARTIAL.
- Thumbnail analysis is text-only unless an image artifact is provided;
  "thumbnail_evaluated" may never be true based on text alone.
- Title/thumbnail scores are heuristic, never CTR / ranking predictions.
- Claims in the final report must be labeled MEASURED / INFERRED / HYPOTHESIS.

Library usage (from tests):
  from audit_manifest import AuditManifest
  m = AuditManifest("strict", "@handle", artifact_destination="D:/YouTube/Audits/November-2026")
  m.record("phase1", "youtube", "ytdata sections ...", exit_code=0, artifact="D:/YouTube/Audits/November-2026/sections.json")
  m.finalize()  # -> dict summary

CLI usage:
  python audit_manifest.py --manifest manifest.json --mode strict --destination D:/YouTube/Audits/November-2026
"""
import argparse
import json
import os
import sys

REQUIRED_PHASES = ["phase1", "phase2", "phase3", "phase4", "phase5", "phase6"]
PHASE_SKILLS = {
    "phase1": "youtube",
    "phase2": "transcript",
    "phase3": "yt-script",
    "phase4": "yt-package",
    "phase5": "youtube",  # keywords/compete/scorecard commands (yt-seo is only invoked if its own skill/script runs)
    "phase6": "youtube",  # outliers (yt-viral is only invoked if its own skill/script runs)
    "phase7": "yt-retention",
}
OPTIONAL_PHASES = {"phase7"}
VALID_STATUSES = {"success", "failed", "blocked", "skipped", "not_run"}


def _status_from_exit_code(exit_code):
    return "success" if exit_code == 0 else "failed"


class AuditManifest:
    """Collect phase records and finalize an audit honestly."""

    def __init__(self, mode="strict", channel=None, artifact_destination=None):
        if mode not in ("strict", "partial"):
            raise ValueError("mode must be 'strict' or 'partial'")
        self.mode = mode
        self.channel = channel
        self.phases = {}
        self.artifacts = {}
        self.claims = []
        self.artifact_destination = None
        self.artifact_policy = "not_set"
        self.artifacts_verified = False
        if artifact_destination:
            self.set_artifact_destination(artifact_destination)

    # ---- Artifact destination policy (see yt-guide SKILL.md — the owning rule) ----

    def set_artifact_destination(self, dest, policy="user_selected"):
        """Select & validate the user-chosen destination directory.

        Rules enforced here:
        - The path must be absolute.
        - It must exist as a directory, or be creatable (missing parent fails).
        - Inaccessible locations raise ValueError — the agent must stop and ask,
          never silently fall back to Temp/Desktop/Downloads/cwd.
        """
        if not isinstance(dest, str) or not dest.strip():
            raise ValueError("artifact_destination must be a non-empty absolute path")
        if not os.path.isabs(dest):
            raise ValueError(f"artifact_destination must be absolute, got: {dest!r}")
        realpath = os.path.realpath(dest)
        if os.path.exists(realpath) and not os.path.isdir(realpath):
            raise ValueError(f"artifact destination is not a directory: {realpath}")
        try:
            os.makedirs(realpath, exist_ok=True)
        except OSError as e:
            raise ValueError(f"artifact destination inaccessible: {e}")
        self.artifact_destination = realpath
        self.artifact_policy = policy
        return realpath

    def _inside_destination(self, path):
        d = self.artifact_destination
        return path == d or path.startswith(d + os.sep)

    def _resolve_artifact(self, artifact):
        """Validate an artifact path against the destination policy.

        Requires: artifact destination already set; path absolute; resolves
        inside the destination (rejects `..` escapes and absolute substitution).
        """
        if self.artifact_destination is None:
            raise ValueError(
                "artifact destination not set — ask the user for the destination directory first; "
                "do not default to Temp/Desktop/Downloads/cwd")
        if not isinstance(artifact, str) or not artifact.strip():
            raise ValueError("artifact path must be a non-empty absolute path")
        if not os.path.isabs(artifact):
            raise ValueError(f"artifact path must be absolute: {artifact!r}")
        resolved = os.path.realpath(artifact)
        if not self._inside_destination(resolved):
            raise ValueError(
                f"artifact escapes selected destination: {artifact!r} "
                f"(destination is {self.artifact_destination})")
        return resolved

    def ensure_artifact_path(self, path, overwrite=False):
        """Pre-write validation for a NEW artifact file.

        - Absolute path required; must resolve inside the destination.
        - Refuses to overwrite an existing file unless overwrite=True
          (caller must have explicit user permission).
        """
        resolved = self._resolve_artifact(path)
        if os.path.exists(resolved) and not overwrite:
            raise FileExistsError(
                f"refusing to overwrite existing file without permission: {resolved}")
        return resolved

    def verify_artifacts(self):
        """Confirm every recorded artifact exists and stays inside the destination."""
        if self.artifact_destination is None:
            self.artifacts_verified = False
            return self.artifacts_verified
        for phase, p in self.artifacts.items():
            if not self._inside_destination(p):
                self.artifacts_verified = False
                return self.artifacts_verified
            if not os.path.exists(p):
                self.artifacts_verified = False
                return self.artifacts_verified
        self.artifacts_verified = True
        return self.artifacts_verified

    def record(self, phase, skill, command, exit_code=None, status=None,
               artifact=None, notes=""):
        """Record a phase. Status defaults to exit-code-derived; explicit
        status wins, but a non-zero exit code can never report success."""
        if status is None:
            status = _status_from_exit_code(exit_code)
        elif status == "success" and exit_code not in (None, 0):
            raise ValueError(
                f"Phase {phase}: status='success' with non-zero exit code {exit_code} is not allowed")
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}, got {status!r}")
        if phase not in PHASE_SKILLS:
            raise ValueError(f"Unknown phase {phase!r}; expected one of {sorted(PHASE_SKILLS)}")
        if skill != PHASE_SKILLS[phase]:
            # Not fatal, but recorded so the report can flag skill/phase mismatch.
            notes = (notes + f" [note: skill '{skill}' != expected '{PHASE_SKILLS[phase]}']").strip()
        self.phases[phase] = {
            "phase": phase,
            "skill": skill,
            "command": command,
            "exit_code": exit_code,
            "status": status,
            "artifact": artifact,
            "notes": notes,
        }
        if artifact:
            if self.artifact_destination is not None:
                artifact = self._resolve_artifact(artifact)
            self.artifacts[phase] = artifact
        return self.phases[phase]

    def add_claim(self, text, evidence="MEASURED"):
        """Track a report claim. evidence must be MEASURED / INFERRED / HYPOTHESIS."""
        if evidence not in ("MEASURED", "INFERRED", "HYPOTHESIS"):
            raise ValueError("evidence must be MEASURED, INFERRED or HYPOTHESIS")
        self.claims.append({"text": text, "evidence": evidence})

    def set_thumbnail_analysis(self, phase, thumbnail_evaluated, basis):
        """Thumbnail analysis must never claim visual evaluation on text alone."""
        if phase not in self.phases:
            raise ValueError(f"Unknown phase {phase!r}")
        if thumbnail_evaluated and basis not in ("image_artifact",):
            raise ValueError(
                "thumbnail_evaluated=True is only allowed with basis='image_artifact'; "
                "text alone cannot prove visual evaluation")
        self.phases[phase]["thumbnail_evaluated"] = thumbnail_evaluated
        self.phases[phase]["thumbnail_basis"] = basis

    def _required_failures(self):
        failed = []
        for ph in REQUIRED_PHASES:
            rec = self.phases.get(ph)
            if rec is None:
                failed.append((ph, "not_run"))
            elif rec["status"] != "success":
                failed.append((ph, rec["status"]))
        return failed

    def finalize(self):
        failed = self._required_failures()
        if failed:
            if self.mode == "strict":
                overall = "FAILED"
                stopped_at = failed[0][0]
            else:
                overall = "PARTIAL"
                stopped_at = None
        else:
            overall = "COMPLETE"
            stopped_at = None
        artifacts_verified = self.verify_artifacts() if self.artifact_destination else False
        return {
            "mode": self.mode,
            "channel": self.channel,
            "artifact_destination": self.artifact_destination,
            "artifact_policy": self.artifact_policy,
            "artifact_list": [rec["artifact"] for rec in self.phases.values() if rec.get("artifact")],
            "artifacts_verified": artifacts_verified,
            "overall": overall,
            "stopped_at_phase": stopped_at,
            "required_failures": failed,
            "phases": [self.phases.get(ph, {
                "phase": ph, "skill": PHASE_SKILLS[ph], "status": "not_run",
                "command": None, "exit_code": None, "artifact": None, "notes": "",
            }) for ph in REQUIRED_PHASES] + [self.phases[ph] for ph in OPTIONAL_PHASES if ph in self.phases],
            "claims": self.claims,
            "heuristic_note": (
                "Title/thumbnail/keyword scores are heuristic signals, not predictions of "
                "YouTube ranking or CTR. Nothing in this manifest should be presented as a "
                "forecast of views, click-through rate, or search placement."
            ),
        }

    def to_dict(self):
        return self.finalize()


def summarize_text(result):
    """Human-readable summary for terminal output / agent report."""
    lines = [f"AUDIT MODE: {result['mode'].upper()}  |  OVERALL: {result['overall']}"]
    lines.append(f"ARTIFACT DESTINATION: {result.get('artifact_destination') or 'NOT SET'}  "
                 f"(policy: {result.get('artifact_policy')}, verified: {result.get('artifacts_verified')})")
    if result.get("artifact_list"):
        lines.append("ARTIFACTS:")
        for p in result["artifact_list"]:
            lines.append(f"  - {p}")
    if result["stopped_at_phase"]:
        lines.append(f"STOPPED AT: {result['stopped_at_phase']} (strict mode)")
    if result["required_failures"]:
        lines.append("REQUIRED FAILURES:")
        for ph, st in result["required_failures"]:
            lines.append(f"  - {ph}: {st}")
    else:
        lines.append("All required phases succeeded.")
    lines.append("Phases:")
    for p in result["phases"]:
        lines.append(f"  {p['phase']:<7} {p['skill']:<12} {p['status'].upper():<8} {p.get('command') or '-'}")
    lines.append(result["heuristic_note"])
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Audit manifest validator/finalizer")
    ap.add_argument("--manifest", required=True, help="Path to manifest JSON produced by the agent")
    ap.add_argument("--mode", default=None, choices=["strict", "partial"],
                    help="Override mode stored in manifest")
    ap.add_argument("--destination", default=None,
                    help="User-selected artifact destination directory (absolute path)")
    args = ap.parse_args()

    with open(args.manifest, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    m = AuditManifest(args.mode or data.get("mode", "strict"),
                      data.get("channel"),
                      artifact_destination=args.destination or data.get("artifact_destination"))
    for ph in REQUIRED_PHASES + list(OPTIONAL_PHASES):
        rec = data.get("phases", {}).get(ph)
        if rec:
            m.record(ph, rec.get("skill", PHASE_SKILLS[ph]),
                     rec.get("command", ""), rec.get("exit_code"),
                     rec.get("status"), rec.get("artifact"), rec.get("notes", ""))
    for c in data.get("claims", []):
        m.add_claim(c.get("text", ""), c.get("evidence", "MEASURED"))
    for ph, rec in (data.get("phases", {}) or {}).items():
        if "thumbnail_evaluated" in rec:
            m.set_thumbnail_analysis(ph, bool(rec["thumbnail_evaluated"]),
                                     rec.get("thumbnail_basis", "text"))

    result = m.finalize()
    print(summarize_text(result))
    print()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["overall"] == "FAILED":
        sys.exit(1)


if __name__ == "__main__":
    main()
