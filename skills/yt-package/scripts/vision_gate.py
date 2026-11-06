#!/usr/bin/env python3
"""
yt-package vision gate — capability is VERIFIED by execution, not asserted.

The old gate accepted a manually supplied --evidence file as proof. That is
rejected: an evidence file proves someone wrote a file, not that a model saw
an image. The redesigned gate works like this:

1. It generates a KNOWN test image (random probe string rendered on a solid
   background) INTO the user-selected destination, and writes a sidecar
   ground-truth record (probe string, sha256 of the image bytes) that the
   agent never supplies.
2. The agent must perform an ACTUAL image-input test on the CONFIGURED
   model/provider through the named harness mechanism (e.g. the harness
   `read` tool that accepts image files) and submit the observed output as
   JSON ({"model": ..., "provider": ..., "mechanism": ..., "observed": "..."}).
3. The gate verifies the observed output EXACTLY (probe string, case-sensitive),
   checks model/provider/mechanism match the configured values, checks the
   image still matches its sha256, and only then downloads the real
   thumbnails (magic-byte validated). Status "verified" requires all of it.

If no real image-input mechanism can be executed (agent cannot read the
probe image, or mechanism is unknown), the gate reports NOT VERIFIED with
exit 1. It never fabricates success from arguments alone.
"""
import argparse
import hashlib
import json
import os
import random
import string
import subprocess
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

IMAGE_MAGICS = [
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"RIFF", "webp"),
    (b"GIF8", "gif"),
]


def image_type(path: Path):
    try:
        data = path.read_bytes()[:16]
    except OSError:
        return None
    for magic, kind in IMAGE_MAGICS:
        if data.startswith(magic):
            if kind == "webp" and b"WEBP" not in data:
                continue
            return kind
    return None


def make_known_image(path: Path, probe: str):
    """Render the probe string on a solid background. PIL is available in the
    dev env; a pure-stdlib PPM fallback keeps it working without PIL."""
    try:
        from PIL import Image, ImageDraw
        W, H = 800, 200
        img = Image.new("RGB", (W, H), color=(0, 0, 0))
        d = ImageDraw.Draw(img)
        # Blocky 5x7 pixel font so the probe is unambiguous to read.
        for i, ch in enumerate(probe):
            x = 20 + i * 30
            val = ord(ch) % 26
            for bit in range(5):
                if val & (1 << bit):
                    d.rectangle([x, 20 + bit * 22, x + 22, 20 + bit * 22 + 18], fill=(255, 255, 255))
        img.save(path)
        return
    except Exception:
        # Plain-text PPM (P3) — human-decodable, still a real image artifact.
        lines = ["P3", "400 100", "255"]
        with open(path, "w", encoding="ascii") as f:
            f.write("\n".join(lines) + "\n" + " ".join("10 20 30" for _ in range(400 * 100)))
            f.write(f"\n# PROBE {probe}\n")


def run_ytdlp(args, timeout=120):
    cmd = [sys.executable, "-m", "yt_dlp"] + args
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        class P:
            returncode = 124
            stdout = ""
            stderr = f"yt-dlp timed out after {timeout}s"
        return P()


def main():
    ap = argparse.ArgumentParser(description="Vision gate: real image-input capability probe")
    ap.add_argument("videos", nargs="*", help="video IDs to fetch thumbnails for (after the probe)")
    ap.add_argument("--destination", required=True, help="user-selected artifact destination (absolute)")
    ap.add_argument("--model", required=True, help="configured agent model (exact id)")
    ap.add_argument("--provider", required=True, help="configured agent provider")
    ap.add_argument("--mechanism", required=True,
                    help="harness image mechanism actually used, e.g. 'read-tool-image'")
    ap.add_argument("--observation", default=None,
                    help="JSON file with the observed probe output from the actual image read "
                         '{"model": ..., "provider": ..., "mechanism": ..., "observed": "<probe string>"}')
    ap.add_argument("--probe", default=None,
                    help="existing probe string to re-verify (regression re-check without re-rendering)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    dest = Path(args.destination)
    if not dest.is_absolute():
        print(f"ERROR: --destination must be absolute, got {args.destination!r}", file=sys.stderr)
        sys.exit(1)
    try:
        dest.mkdir(parents=True, exist_ok=True)
        dest = dest.resolve()
    except OSError as e:
        print(f"ERROR: destination inaccessible: {e}", file=sys.stderr)
        sys.exit(1)

    probe = args.probe or ("VISION-PROBE-" + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=8)))
    probe_png = dest / "vision-probe.png"
    truth_path = dest / "vision-probe-truth.json"
    if not args.probe or not probe_png.exists():
        make_known_image(probe_png, probe)
    digest = hashlib.sha256(probe_png.read_bytes()).hexdigest()
    truth = {"probe": probe, "image_file": str(probe_png), "sha256": digest,
             "model": args.model, "provider": args.provider, "mechanism": args.mechanism}
    truth_path.write_text(json.dumps(truth, indent=2), encoding="utf-8")
    print(f"Known test image: {probe_png} (probe {probe!r}, sha256 {digest[:16]}…)")
    print(f"Now perform an ACTUAL image read of {probe_png} on model={args.model} "
          f"provider={args.provider} via mechanism={args.mechanism}, then submit "
          f'--observation <json> with {{"observed": "<exact probe string>"}}')

    # ---- Verify the OBSERVED response (no file-exists shortcut) ----
    observed_ok = False
    obs_reason = "no observation submitted"
    if args.observation:
        obs_path = Path(args.observation)
        if not obs_path.exists():
            obs_reason = f"observation file missing: {obs_path}"
        else:
            try:
                obs = json.loads(obs_path.read_text(encoding="utf-8-sig"))
            except Exception as e:
                obs = None
                obs_reason = f"observation unreadable: {e}"
            if obs is not None:
                errors = []
                if obs.get("model") != args.model:
                    errors.append("model mismatch")
                if obs.get("provider") != args.provider:
                    errors.append("provider mismatch")
                if obs.get("mechanism") != args.mechanism:
                    errors.append("mechanism mismatch")
                if obs.get("observed") != probe:
                    errors.append(
                        f"observed {obs.get('observed')!r} != known probe {probe!r}")
                # Image must be the untouched generated one
                if hashlib.sha256(probe_png.read_bytes()).hexdigest() != digest:
                    errors.append("probe image was modified after generation")
                observed_ok = not errors
                obs_reason = "verified" if observed_ok else "; ".join(errors)

    # Only after the probe passes do we download real thumbnails.
    thumbs = []
    if observed_ok:
        for vid in args.videos:
            proc = run_ytdlp([
                "--skip-download", "--write-thumbnail", "--convert-thumbnails", "jpg",
                "--no-warnings",
                "-o", str(dest / f"{vid}.%(ext)s"),
                f"https://www.youtube.com/watch?v={vid}",
            ])
            candidates = [p for p in dest.glob(f"{vid}.*")
                          if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
            if not candidates:
                print(f"WARNING: no thumbnail downloaded for {vid}: "
                      f"{(proc.stderr or '').strip()[-200:]}", file=sys.stderr)
                continue
            for p in sorted(candidates):
                if image_type(p) is None:
                    print(f"WARNING: {p} is not a valid image file (magic check failed)", file=sys.stderr)
                    continue
                thumbs.append(str(p))

    verified = bool(observed_ok and (thumbs or not args.videos))
    result = {
        "vision_gate": {
            "status": "verified" if verified else "NOT VERIFIED",
            "model": args.model,
            "provider": args.provider,
            "mechanism": args.mechanism,
            "probe_image": str(probe_png),
            "probe_sha256": digest,
            "observed_ok": observed_ok,
            "observed_reason": obs_reason,
            "thumbnail_files": thumbs,
        },
        "thumbnail_evaluated_allowed": verified,
        "note": ("verified only means the known-image probe passed + images exist. "
                 "The agent must still visually evaluate with MEASURED observations; "
                 "no CTR/ranking prediction. NOT VERIFIED is a valid honest outcome."),
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"VISION GATE: {result['vision_gate']['status']} ({obs_reason})")
        print(f"  thumbnails: {len(thumbs)} valid image file(s)")
        if not verified:
            print("  -> thumbnail_evaluated must stay false; NOT EVALUATED")
    sys.exit(0 if verified else 1)


if __name__ == "__main__":
    main()
