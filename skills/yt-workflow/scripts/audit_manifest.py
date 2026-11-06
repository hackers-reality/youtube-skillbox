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
        self._artifact_inventory = []
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

    def record(self, phase, skill, command, exit_code=None, status=None,
               artifact=None, notes="", artifact_type=None, producing_phase=None):
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
            self._register_artifact(
                artifact,
                artifact_type or self._infer_type(artifact),
                producing_phase or phase,
            )
        return self.phases[phase]

    # ---- Artifact inventory ----

    _IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    _TYPE_MAP = {
        ".json": "extracted_data",
        ".csv": "extracted_data",
        ".tsv": "extracted_data",
        ".zip": "extracted_archive",
        ".txt": "log",
        ".log": "log",
        ".md": "report",
        ".html": "report",
        ".pdf": "report",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".webp": "image",
        ".gif": "image",
        ".mp4": "image",
        ".sbv": "subtitles",
        ".vtt": "subtitles",
        ".srt": "subtitles",
        ".xml": "extracted_data",
        ".yaml": "extracted_data",
    }

    @classmethod
    def _infer_type(cls, path):
        ext = os.path.splitext(str(path))[1].lower()
        return cls._TYPE_MAP.get(ext, "intermediate")

    def _register_artifact(self, path, artifact_type=None, producing_phase=None):
        """Register one inventory entry for a generated user-facing artifact."""
        resolved = os.path.realpath(path)
        existing = next((e for e in self._artifact_inventory if e["path"] == resolved), None)
        if existing is not None:
            if artifact_type:
                existing["type"] = artifact_type
            if producing_phase is not None:
                existing["phase"] = producing_phase
            existing["verified"] = os.path.exists(resolved)
            return existing
        entry = {
            "path": resolved,
            "type": artifact_type or "intermediate",
            "phase": producing_phase,
            "verified": os.path.exists(resolved),
        }
        self._artifact_inventory.append(entry)
        return entry

    def register_artifact(self, path, artifact_type=None, producing_phase=None):
        """Public helper for agents to register intermediates that aren't a phase cell."""
        if self.artifact_destination is not None:
            path = self._resolve_artifact(path)
        return self._register_artifact(
            path,
            artifact_type or self._infer_type(path),
            producing_phase)

    def list_artifacts(self):
        return list(self._artifact_inventory)

    def verify_artifacts(self):
        """Confirm every artifact in the destination is accounted for and intact.

        Two checks:
        1. Every registered inventory entry is an existing file/dir inside the
           destination.
        2. No unregistered user-facing files are squatting in the destination —
           if files exist on disk that the manifest never claimed, verification
           fails and the unclaimed files are reported.
        """
        if self.artifact_destination is None:
            self.artifacts_verified = False
            return self.artifacts_verified
        inventory_paths = {e["path"] for e in self._artifact_inventory}
        for entry in self._artifact_inventory:
            if not self._inside_destination(entry["path"]):
                self.artifacts_verified = False
                return self.artifacts_verified
            if not os.path.exists(entry["path"]):
                self.artifacts_verified = False
                return self.artifacts_verified
            entry["verified"] = True
        # scan for unregistered squatters (user-facing files the manifest never
        # claimed); exclude empty manifest placeholder if agent is still writing it
        stray = []
        for root, _dirs, files in os.walk(self.artifact_destination):
            for name in files:
                full = os.path.realpath(os.path.join(root, name))
                if full not in inventory_paths:
                    stray.append(full)
        if stray:
            self.artifacts_verified = False
            self.unclaimed_artifacts = stray
            return self.artifacts_verified
        self.artifacts_verified = True
        return self.artifacts_verified

    def add_claim(self, text, evidence="MEASURED"):
        """Track a report claim. evidence must be MEASURED / INFERRED / HYPOTHESIS."""
        if evidence not in ("MEASURED", "INFERRED", "HYPOTHESIS"):
            raise ValueError("evidence must be MEASURED, INFERRED or HYPOTHESIS")
        self.claims.append({"text": text, "evidence": evidence})

    def set_thumbnail_analysis(self, phase, thumbnail_evaluated, basis,
                               image_artifact_path=None):
        """Thumbnail analysis must never claim visual evaluation on text alone.

        - basis='image_artifact' AND thumbnail_evaluated=True requires that an
          image artifact (or the file itself) was registered/provided inside the
          destination. It must exist on disk.
        - basis='user_supplied_text' AND thumbnail_evaluated=False is fine.
        - Otherwise the claim is rejected.
        """
        if phase not in self.phases:
            raise ValueError(f"Unknown phase {phase!r}")
        if thumbnail_evaluated:
            if basis != "image_artifact":
                raise ValueError(
                    "thumbnail_evaluated=True is only allowed with basis='image_artifact'; "
                    "text alone cannot prove visual evaluation")
            if image_artifact_path is None:
                image_artifact_path = self.phases[phase].get("artifact")
            if not image_artifact_path:
                raise ValueError(
                    "thumbnail_evaluated=True requires an actual image artifact path (or the "
                    "phase's registered artifact) pointing at an image file inside the destination")
            resolved_image = image_artifact_path
            if self.artifact_destination is not None:
                try:
                    resolved_image = self._resolve_artifact(image_artifact_path)
                except ValueError as e:
                    raise ValueError(f"image artifact for thumbnail analysis rejected: {e}")
            if not os.path.exists(resolved_image):
                raise ValueError(
                    f"image artifact for thumbnail analysis does not exist on disk: {resolved_image}")
            ext = os.path.splitext(resolved_image)[1].lower()
            if ext not in self._IMAGE_EXT:
                raise ValueError(
                    f"thumbnail artifact must be an image file (jpg/png/webp), got {ext!r}: {resolved_image}")
        # register the image artifact so the inventory is complete
        if image_artifact_path is not None:
            try:
                resolved = self._resolve_artifact(image_artifact_path) if self.artifact_destination else image_artifact_path
                self._register_artifact(resolved, "thumbnail_image", phase)
            except ValueError:
                pass
        self.phases[phase]["thumbnail_evaluated"] = thumbnail_evaluated
        self.phases[phase]["thumbnail_basis"] = basis

    # ---- Vision gate (documented capability test — cannot be inferred) ----

    def record_vision_gate(self, status, model=None, provider=None, mechanism=None,
                           evidence_path=None, thumbnail_files=None,
                           probe=None, observed=None):
        """Record the autonomous vision-gate outcome.

        status: "verified" only when a known-image capability test actually
        passed on the current model via a named mechanism AND downloaded
        thumbnail artifacts exist inside the destination. When probe/observed
        are supplied they must match exactly — an evidence file alone is NOT
        proof. Anything else is "unverified"/"failed" — thumbnail_evaluated
        must stay false.
        """
        if status not in ("verified", "unverified", "failed"):
            raise ValueError(f"vision gate status must be verified/unverified/failed, got {status!r}")
        files = list(thumbnail_files or [])
        if status == "verified":
            if not model or not provider or not mechanism:
                raise ValueError("verified vision gate requires model, provider and mechanism")
            if not evidence_path or not os.path.exists(evidence_path):
                raise ValueError("verified vision gate requires an existing evidence file "
                                 "(known-image test result) on disk")
            if probe is not None and observed is not None and observed != probe:
                raise ValueError(f"verified vision gate requires observed == known probe; "
                                 f"got observed={observed!r} probe={probe!r}")
            if not files:
                raise ValueError("verified vision gate requires downloaded thumbnail files")
            for f in files:
                if self.artifact_destination is not None:
                    self._resolve_artifact(f)
                if not os.path.exists(f):
                    raise ValueError(f"vision gate thumbnail file does not exist: {f}")
                ext = os.path.splitext(f)[1].lower()
                if ext not in self._IMAGE_EXT:
                    raise ValueError(f"vision gate thumbnail must be an image file, got {ext!r}")
        self.vision_gate = {
            "status": status,
            "model": model,
            "provider": provider,
            "mechanism": mechanism,
            "evidence_path": evidence_path,
            "thumbnail_files": files,
            "probe": probe,
            "observed": observed,
        }
        return self.vision_gate

    def write_manifest(self, path, overwrite=False):
        """Finalize and persist the manifest so the saved file agrees with the
        validator: artifacts_verified / overall_status are the FINAL values,
        not the construction-time defaults. The manifest registers itself so
        verify_artifacts() never reports it as unclaimed."""
        resolved = os.path.realpath(path)
        if self.artifact_destination is not None:
            if not self._inside_destination(resolved):
                raise ValueError(f"manifest escapes selected destination: {resolved}")
            self._register_artifact(resolved, "audit_manifest", "manifest")
        if os.path.exists(resolved) and not overwrite:
            # Re-check nothing changed structurewise — overwrite only when invited.
            pass
        if not os.path.exists(resolved):
            # Placeholder so verify_artifacts() sees the manifest itself as claimed.
            with open(resolved, "w", encoding="utf-8") as f:
                f.write("{}")
        summary = self.finalize()
        to_write = dict(summary)
        to_write["overall_status"] = summary["overall"]  # alias the saved file must carry
        to_write["phases_dict"] = {ph: rec for ph, rec in self.phases.items()}
        # Keep the dict shape loadable by the CLI validator: expose phases in
        # the dict form it reads, while finalize() stays the canonical view.
        to_write["phases"] = {ph: rec for ph, rec in self.phases.items()}
        # The finalized overall (FAILED/PARTIAL/COMPLETE) is authoritative;
        # store it under both keys so saved == validator output.
        with open(resolved, "w", encoding="utf-8") as f:
            json.dump(to_write, f, indent=2, ensure_ascii=False)
        return to_write

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
            "artifact_inventory": self.list_artifacts(),
            "artifacts_verified": artifacts_verified,
            "unclaimed_artifacts": getattr(self, "unclaimed_artifacts", []),
            "overall": overall,
            "overall_status": overall,
            "stopped_at_phase": stopped_at,
            "required_failures": failed,
            "phases": [self.phases.get(ph, {
                "phase": ph, "skill": PHASE_SKILLS[ph], "status": "not_run",
                "command": None, "exit_code": None, "artifact": None, "notes": "",
            }) for ph in REQUIRED_PHASES] + [self.phases[ph] for ph in OPTIONAL_PHASES if ph in self.phases],
            "claims": self.claims,
            "vision_gate": getattr(self, "vision_gate", None),
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
    inv = result.get("artifact_inventory", [])
    if inv:
        lines.append("ARTIFACTS:")
        for entry in inv:
            lines.append(f"  - [{entry.get('type', '?'):<14}] {entry.get('phase') or '-':<8} "
                         f"{'OK' if entry.get('verified') else 'MISSING'} {entry['path']}")
    unclaimed = result.get("unclaimed_artifacts", [])
    if unclaimed:
        lines.append("UNCLAIMED ARTIFACTS (files in destination not recorded):")
        for p in unclaimed:
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
    ap.add_argument("--write", action="store_true",
                    help="Rewrite the manifest file with final artifacts_verified "
                         "and overall_status so the saved file agrees with this "
                         "validator run (default: print only).")
    args = ap.parse_args()

    with open(args.manifest, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    m = AuditManifest(args.mode or data.get("mode", "strict"),
                      data.get("channel"),
                      artifact_destination=args.destination or data.get("artifact_destination"))
    # The manifest itself is a generated workflow artifact.
    manifest_path = os.path.realpath(args.manifest)
    if m.artifact_destination and m._inside_destination(manifest_path):
        m.register_artifact(manifest_path, artifact_type="audit_manifest", producing_phase="manifest")
    for entry in data.get("artifact_inventory", []):
        if isinstance(entry, dict) and entry.get("path"):
            m.register_artifact(entry["path"], entry.get("type"), entry.get("phase"))
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
            m.set_thumbnail_analysis(
                ph, bool(rec["thumbnail_evaluated"]),
                rec.get("thumbnail_basis", "text"),
                image_artifact_path=(rec.get("image_artifact_path") or rec.get("image_artifact")))
    if data.get("vision_gate"):
        vg = data["vision_gate"]
        try:
            m.record_vision_gate(vg.get("status", "unverified"),
                                 model=vg.get("model"), provider=vg.get("provider"),
                                 mechanism=vg.get("mechanism"),
                                 evidence_path=vg.get("evidence_path"),
                                 thumbnail_files=vg.get("thumbnail_files"))
        except ValueError:
            m.vision_gate = {"status": "unverified", "error": "saved record failed re-validation"}

    result = m.finalize()
    if args.write:
        # Persist FINAL artifacts_verified + overall_status back to disk.
        m.write_manifest(args.manifest, overwrite=True)
        result = m.finalize()
    print(summarize_text(result))
    print()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["overall"] == "FAILED":
        sys.exit(1)


if __name__ == "__main__":
    main()
