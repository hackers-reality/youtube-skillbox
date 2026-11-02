#!/usr/bin/env python3
"""
yt-workflow: Orchestrate multi-skill YouTube audit.

Usage:
    python run_audit.py @handle [--outdir DIR] [--skip-phases PHASES]

Phases:
  1. youtube    - Channel data (sections, videos, home, profile)
  2. transcript - Transcripts for top 3 videos
  3. script     - Hook scores from transcripts
  4. package    - Title/thumbs scores
  5. seo        - Keywords, competition, scorecards
  6. viral      - Outliers, competitor analysis
  7. audit      - Synthesis (requires all above)
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
YTDATA = REPO_ROOT / "skills" / "youtube" / "scripts" / "ytdata.py"
GETTRANSCRIPT = REPO_ROOT / "skills" / "transcript" / "scripts" / "gettranscript.py"

PHASES = ["youtube", "transcript", "script", "package", "seo", "viral", "audit"]

def run(cmd, cwd=None):
    """Run command, return (success, stdout, stderr)."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or REPO_ROOT)
    if result.returncode != 0:
        print(f"    FAILED: {result.stderr[:200]}")
    return result.returncode == 0, result.stdout, result.stderr

def phase_youtube(handle, outdir, limit=20):
    """Collect channel data."""
    print("\n=== Phase 1: YouTube Data ===")
    out = {}
    for cmd, key in [
        (["profile", handle], "profile"),
        (["sections", handle], "sections"),
        (["channel", handle, "--limit", str(limit), "--with-duration"], "channel"),
        (["latest", handle, "--limit", "10", "--with-duration"], "latest"),
        (["home", handle], "home"),
    ]:
        ok, out_json, _ = run(["python", str(YTDATA), *cmd, "--json"])
        out[key] = json.loads(out_json) if ok and out_json else None
        if not ok:
            print(f"  WARNING: {key} failed")
    # Save
    with open(outdir / "01_youtube.json", "w") as f:
        json.dump(out, f, indent=2)
    return out

def get_top_videos(youtube_data, n=3):
    """Extract top N videos by views from channel data."""
    videos = youtube_data.get("channel", [])
    # Sort by views desc
    videos = [v for v in videos if v.get("views") is not None]
    videos.sort(key=lambda v: v.get("views", 0), reverse=True)
    return videos[:n]

def phase_transcript(handle, youtube_data, outdir, n=3):
    """Fetch transcripts for top N videos."""
    print("\n=== Phase 2: Transcripts ===")
    top = get_top_videos(outdir.parent.joinpath("01_youtube.json").read_text() if False else [], n)
    # Load youtube data
    with open(outdir / "01_youtube.json") as f:
        yt = json.load(f)
    top = get_top_videos(yt, n)
    transcripts = []
    for v in top:
        vid = v.get("id")
        if not vid:
            continue
        print(f"  Fetching transcript for {vid}...")
        ok, out, _ = run(["python", str(GETTRANSCRIPT), vid, "--format", "json"])
        if ok and out:
            t = json.loads(out)
            t["video_id"] = vid
            t["title"] = v.get("title")
            t["views"] = v.get("views")
            transcripts.append(t)
        else:
            print(f"  WARNING: failed to get transcript for {vid}")
    with open(outdir / "02_transcripts.json", "w") as f:
        json.dump(transcripts, f, indent=2)
    return transcripts

def phase_script(transcripts, outdir):
    """Score hooks from transcripts."""
    print("\n=== Phase 3: Hook Scoring ===")
    # This would call yt-script/hookscore.py if it exists
    # For now, placeholder
    print("  TODO: implement hookscore.py")
    return []

def phase_package(youtube_data, outdir):
    """Score titles/thumbnails."""
    print("\n=== Phase 4: Title/Thumbnail Audit ===")
    with open(outdir / "01_youtube.json") as f:
        yt = json.load(f)
    top = get_top_videos(yt, 10)
    titles = [v.get("title", "") for v in top]
    with open(outdir / "titles.txt", "w") as f:
        f.write("\n".join(titles))
    print("  TODO: implement title.py scoring")
    return []

def phase_seo(handle, outdir):
    """Keyword research + competition."""
    print("\n=== Phase 5: SEO / Keywords ===")
    # Extract niche from channel description/profile
    with open(outdir / "01_youtube.json") as f:
        yt = json.load(f)
    profile = yt.get("profile", {})
    tags = profile.get("tags", [])
    niche = " ".join(tags[:3]) if tags else "general"
    print(f"  Niche detected: {niche}")
    print("  TODO: implement keywords/competing/scorecard")
    return []

def phase_viral(handle, outdir):
    """Outliers + competitor analysis."""
    print("\n=== Phase 6: Viral / Outliers ===")
    print("  TODO: implement viral.py")
    return []

def phase_audit(all_data, outdir):
    """Final synthesis."""
    print("\n=== Phase 7: Final Audit ===")
    print("  TODO: implement final synthesis")
    return {}

def main():
    parser = argparse.ArgumentParser(description="Run full YouTube channel audit")
    parser.add_argument("handle", help="@handle or channel URL")
    parser.add_argument("--outdir", default=None, help="Output directory")
    parser.add_argument("--limit", type=int, default=20, help="Max videos to analyze")
    parser.add_argument("--skip", nargs="*", default=[], help="Phases to skip")
    args = parser.parse_args()

    outdir = Path(args.outdir) if args.outdir else Path(tempfile.mkdtemp(prefix="yt_audit_"))
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {outdir}")

    # Phase 1
    if "youtube" not in args.skip:
        yt_data = phase_youtube(args.handle, outdir, args.limit)
    else:
        with open(outdir / "01_youtube.json") as f:
            yt_data = json.load(f)

    # Phase 2
    if "transcript" not in args.skip:
        phase_transcript(args.handle, yt_data, outdir)

    # Remaining phases (placeholders)
    if "script" not in args.skip:
        phase_script([], outdir)
    if "package" not in args.skip:
        phase_package(yt_data, outdir)
    if "seo" not in args.skip:
        phase_seo(args.handle, outdir)
    if "viral" not in args.skip:
        phase_viral(args.handle, outdir)
    if "audit" not in args.skip:
        phase_audit({}, outdir)

    print(f"\n✅ Audit complete. Output in: {outdir}")

if __name__ == "__main__":
    main()