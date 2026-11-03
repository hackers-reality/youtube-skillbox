#!/usr/bin/env python3
"""
YouTube transcript + metadata via yt-dlp. No API key, no credits.

Usage:
  python gettranscript.py <url-or-id> [--format text|stamped|json] [--lang en,hi,...]

Formats:
  text     Clean spoken text, no timestamps (good for summarizing/translating)
  stamped  [MM:SS] line per segment (good for quoting specific moments)
  json     Structured: {"video_id","language","generated","transcript":[{"text","start","duration"}],"metadata":{...}}

Notes:
  - Prefers manual captions, falls back to auto-generated.
  - --lang is a priority list (first that exists wins). Default: en.
  - Requires: pip install yt-dlp   (Python 3.9+)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

# Force UTF-8 output (Windows console defaults to cp1252 which breaks on ♪ etc.)
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def run_ytdlp(args):
    """Invoke yt-dlp as a module (works even when the exe isn't on PATH)."""
    cmd = [sys.executable, "-m", "yt_dlp"] + args
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def normalize_id(url_or_id):
    """Accept a full URL, a youtu.be link, shorts, or a bare 11-char ID."""
    s = url_or_id.strip()
    if re.fullmatch(r"[\w-]{11}", s):
        return s
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})", s)
    if m:
        return m.group(1)
    return s  # let yt-dlp figure it out


def fetch_subtitle_files(vid, langs, all_langs=False):
    """Download subtitle json3 files to a temp dir. Returns (list_of_paths, used_lang)."""
    tmpdir = tempfile.mkdtemp(prefix="ytdlp_")
    if all_langs:
        langspec = "all"
    else:
        langspec = ",".join(langs) + ".*"
    args = [
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", langspec,
        "--sub-format", "json3",
        "--no-warnings",
        "-o", os.path.join(tmpdir, "%(id)s"),
        f"https://www.youtube.com/watch?v={vid}",
    ]
    proc = run_ytdlp(args)
    files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".json3")]

    if not files:
        # Surface a useful reason instead of a silent empty result.
        err = (proc.stderr or "").strip().splitlines()
        hint = err[-1] if err else "no subtitle track found"
        die(f"Could not fetch a transcript for {vid}. {hint}\n"
            f"The video may have captions disabled, be private/age-restricted, "
            f"or not have any of: {', '.join(langs) if not all_langs else 'any language'}")

    if all_langs:
        return files, None
    
    # Prefer exact-language matches (e.g. '.en.json3') over translated ('.en-de.json3').
    def rank(path):
        name = os.path.basename(path)
        for i, lg in enumerate(langs):
            if re.search(rf"\.{re.escape(lg)}(-orig)?\.json3$", name) or name.endswith(f".{lg}.json3"):
                return (i, 0 if "orig" in name or "-orig" in name else 1)
        return (len(langs), 2)

    files.sort(key=rank)
    return files, files[0]


def parse_json3(path):
    """Parse YouTube json3 caption events into [{'text','start','duration'}]."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    segs = []
    for ev in data.get("events", []):
        if "segs" not in ev:
            continue
        text = "".join(s.get("utf8", "") for s in ev["segs"])
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        start_ms = ev.get("tStartMs", 0)
        dur_ms = ev.get("dDurationMs", 0)
        segs.append({
            "text": text,
            "start": round(start_ms / 1000.0, 3),
            "duration": round(dur_ms / 1000.0, 3),
        })
    return segs


def guess_lang(path):
    m = re.search(r"\.([a-z]{2,}(?:-[A-Za-z0-9]+)?)\.json3$", os.path.basename(path))
    return m.group(1) if m else "unknown"


def is_generated(path):
    name = os.path.basename(path)
    return not bool(re.search(r"-orig\.json3$", name)) and "orig" not in name


def fetch_metadata(vid):
    """Grab title/channel/etc via a single yt-dlp metadata dump."""
    args = ["--skip-download", "--no-warnings", "--dump-single-json",
            f"https://www.youtube.com/watch?v={vid}"]
    proc = run_ytdlp(args)
    if proc.returncode != 0 or not proc.stdout.strip():
        return {}
    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}
    return {
        "title": info.get("title"),
        "author_name": info.get("channel") or info.get("uploader"),
        "author_url": info.get("channel_url") or info.get("uploader_url"),
        "thumbnail_url": info.get("thumbnail"),
        "duration_seconds": info.get("duration"),
        "view_count": info.get("view_count"),
        "upload_date": info.get("upload_date"),
        "description": (info.get("description") or "")[:500] or None,
    }


def to_stamped(segs):
    out = []
    for s in segs:
        total = int(s["start"])
        mm, ss = divmod(total, 60)
        out.append(f"[{mm:02d}:{ss:02d}] {s['text']}")
    return "\n".join(out)


def to_text(segs):
    return " ".join(s["text"] for s in segs)


def main():
    ap = argparse.ArgumentParser(description="Fetch a YouTube transcript via yt-dlp (no API key).")
    ap.add_argument("url", help="YouTube URL or 11-char video ID")
    ap.add_argument("--format", default="text", choices=["text", "stamped", "json"],
                    help="Output format (default: text)")
    ap.add_argument("--lang", default="en",
                    help="Comma-separated language priority list (default: en)")
    ap.add_argument("--all-langs", action="store_true",
                    help="Fetch ALL available subtitle tracks (manual + auto) and return all in JSON")
    ap.add_argument("--no-meta", action="store_true", help="Skip metadata lookup (faster)")
    args = ap.parse_args()

    try:
        import yt_dlp  # noqa: F401  (probe that it's installed)
    except ImportError:
        die("yt-dlp is not installed. Run: pip install yt-dlp")

    vid = normalize_id(args.url)
    langs = [l.strip() for l in args.lang.split(",") if l.strip()]

    if args.all_langs:
        files, _ = fetch_subtitle_files(vid, langs, all_langs=True)
        if not files:
            die("No subtitle tracks found for this video.")
        
        all_transcripts = []
        for subfile in files:
            segs = parse_json3(subfile)
            if not segs:
                continue
            all_transcripts.append({
                "language": guess_lang(subfile),
                "generated": is_generated(subfile),
                "segment_count": len(segs),
                "transcript": segs,
            })
        
        if not all_transcripts:
            die("Transcript files were empty — the tracks may have no text cues.")
        
        meta = {} if args.no_meta else fetch_metadata(vid)
        payload = {
            "video_id": vid,
            "transcripts": all_transcripts,
            "metadata": meta or None,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    _, subfile = fetch_subtitle_files(vid, langs)
    segs = parse_json3(subfile)

    if not segs:
        die("Transcript file was empty — the track may have no text cues.")

    meta = {} if args.no_meta else fetch_metadata(vid)

    if args.format == "json":
        payload = {
            "video_id": vid,
            "language": guess_lang(subfile),
            "generated": is_generated(subfile),
            "segment_count": len(segs),
            "metadata": meta or None,
            "transcript": segs,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.format == "stamped":
        print(to_stamped(segs))
    else:
        print(to_text(segs))


if __name__ == "__main__":
    main()
