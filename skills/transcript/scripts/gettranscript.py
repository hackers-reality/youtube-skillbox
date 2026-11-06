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


def run_ytdlp(args, timeout=120):
    """Invoke yt-dlp as a module (works even when the exe isn't on PATH)."""
    cmd = [sys.executable, "-m", "yt_dlp"] + args
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        class _TimeoutProc:
            returncode = 124
            stdout = ""
            stderr = f"yt-dlp timed out after {timeout}s: {exc}"
        return _TimeoutProc()


def normalize_id(url_or_id):
    """Accept a full URL, a youtu.be link, shorts, or a bare 11-char ID."""
    s = url_or_id.strip()
    if re.fullmatch(r"[\w-]{11}", s):
        return s
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})", s)
    if m:
        return m.group(1)
    return s  # let yt-dlp figure it out


def _is_429(proc):
    """Precise 429 detection (not a broad 'rate' substring)."""
    err = (getattr(proc, "stderr", "") or "").lower()
    import re as _re
    return bool(_re.search(r"\b429\b", err) or "too many requests" in err or "rate-limited" in err or "rate limited" in err)


def fetch_subtitle_files(vid, langs, all_langs=False, work_dir=None,
                         retries=int(os.environ.get("YTDLP_RETRIES", "3")),
                         sleep=float(os.environ.get("YTDLP_RETRY_SLEEP", "1.0"))):
    """Download subtitle json3 files. Returns (list_of_paths, used_lang).

    Integrity rules (CRITICAL):
    - Only files whose basename starts with f"{vid}." belong to this video.
      Stale .json3 files from OTHER videos sharing the same --work-dir are
      NEVER returned (this was the Earth-spin/Marathi cross-contamination bug:
      os.listdir + endswith(".json3") picked up a previous video's .en.json3).
    - Only files written/modified by THIS invocation qualify (snapshot of
      mtimes before spawn); a stale same-video file from an earlier run with a
      different language cannot be selected either.
    - Any mismatch (no qualifying file, or metadata id != vid) fails — a
      non-zero exit, never a silent wrong-video transcript.
    - HTTP 429 gets bounded retry/backoff. After retries, an explicit failure
      is raised; --all-langs NEVER falls back to a single language.
    """
    tmpdir = work_dir if work_dir else tempfile.mkdtemp(prefix="ytdlp_")
    os.makedirs(tmpdir, exist_ok=True)
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
        "--retries", "10",
        "--extractor-retries", "10",
        "--retry-sleep", "http:linear=2::5",
        "--retry-sleep", "extractor:exp=2:60",
        "--sleep-subtitles", "2",
        "--sleep-requests", "1.5",
        "-o", os.path.join(tmpdir, "%(id)s"),
        f"https://www.youtube.com/watch?v={vid}",
    ]
    # Snapshot before spawn so stale files can never qualify.
    before = {}
    for name in os.listdir(tmpdir):
        try:
            before[name] = os.path.getmtime(os.path.join(tmpdir, name))
        except OSError:
            continue

    proc = None
    attempt = 0
    while True:
        attempt += 1
        proc = run_ytdlp(args, timeout=180)
        # yt-dlp retries internally (--retries for HTTP, --extractor-retries
        # for extractor) with --retry-sleep backoff; this outer loop adds a
        # second bounded 429 backoff across invocations. Either way,
        # exhaustion is an explicit failure — never a single-language fallback.
        if not _is_429(proc) or attempt > retries:
            break
        import time as _time
        _time.sleep(sleep * (2 ** (attempt - 1)))
    if proc is not None and _is_429(proc):
        die(f"ALL-LANGS transcript fetch failed for {vid}: HTTP 429 Too Many Requests "
            f"after {retries} retries (explicit failure, no silent downgrade). "
            f"Last error: {(proc.stderr or '').strip().splitlines()[-1] if proc.stderr else 'no stderr'}")
    # Non-zero yt-dlp exits must NEVER silently produce a successful result —
    # even partial file sets are failures (no incomplete --all-langs).
    if proc is not None and getattr(proc, "returncode", 0) not in (0, None):
        err = (proc.stderr or "").strip().splitlines()
        die(f"Transcript fetch failed for {vid} (yt-dlp exit {proc.returncode}): "
            f"{err[-1] if err else 'no stderr'} -- refusing to return a partial result.")
    files = []
    for name in os.listdir(tmpdir):
        if not name.endswith(".json3"):
            continue
        if not name.startswith(f"{vid}."):
            continue  # belongs to a different video — never return it
        full = os.path.join(tmpdir, name)
        try:
            mtime = os.path.getmtime(full)
        except OSError:
            continue
        if name in before and mtime <= before[name]:
            continue  # stale leftover from an earlier run — disqualify
        files.append(full)

    if not files:
        # Surface a useful reason instead of a silent empty result.
        err = (proc.stderr or "").strip().splitlines() if proc else []
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
        "id": info.get("id"),
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


def _normalize_argv(argv):
    """YouTube video IDs are 11 chars from [A-Za-z0-9_-]; some start with '-'
    (e.g. '-xvOxbvnXuk'). argparse would parse such an ID as a flag, so a
    SINGLE leading dash + 10 valid ID chars is rewritten as a youtu.be URL.

    Rules:
    - Any arg starting with '--' is ALWAYS treated as a flag, never an ID
      (so --all-langs, --full-meta, --min-ratio are untouched).
    - Only single-dash 11-char args that are valid IDs get rewritten.
    - URLs, handles and ordinary flags pass through unchanged.
    """
    out = []
    for arg in argv:
        if arg.startswith("--"):
            # Double-hyphen args are always options/flags (argparse "--" separator included)
            out.append(arg)
        elif re.fullmatch(r"-[A-Za-z0-9_-]{10}", arg):
            out.append(f"https://youtu.be/{arg}")
        else:
            out.append(arg)
    return out


def _validate_video_identity(vid, meta):
    """Refuse to emit a payload whose identity doesn't match the request.

    `meta` is {} when the metadata lookup failed — validation is only
    enforceable when we have a returned id. A mismatch is fatal (exit 1),
    never a silent substitution. Returns the verified video id.
    """
    if meta and meta.get("id"):
        if meta["id"] != vid:
            die(f"Video identity mismatch: transcript requested for {vid} but "
                f"metadata identifies {meta['id']!r} ({meta.get('title')!r}). "
                f"Refusing to return cross-video audio.")
        return meta["id"]
    return vid


def main():
    ap = argparse.ArgumentParser(description="Fetch a YouTube transcript via yt-dlp (no API key).")
    ap.add_argument("url", help="YouTube URL or 11-char video ID")
    ap.add_argument("--format", default="text", choices=["text", "stamped", "json"],
                    help="Output format (default: text)")
    ap.add_argument("--lang", default="en",
                    help="Comma-separated language priority list (default: en)")
    ap.add_argument("--all-langs", action="store_true",
                    help="Fetch ALL available subtitle tracks (manual + auto) and return all in JSON")
    ap.add_argument("--work-dir", default=None,
                    help="Directory for downloaded caption intermediates; use the user-selected artifact destination in workflow runs")
    ap.add_argument("--no-meta", action="store_true", help="Skip metadata lookup (faster)")
    args = ap.parse_args(_normalize_argv(sys.argv[1:]))

    try:
        import yt_dlp  # noqa: F401  (probe that it's installed)
    except ImportError:
        die("yt-dlp is not installed. Run: pip install yt-dlp")

    vid = normalize_id(args.url)
    langs = [l.strip() for l in args.lang.split(",") if l.strip()]

    if args.all_langs:
        try:
            files, _ = fetch_subtitle_files(vid, langs, all_langs=True, work_dir=args.work_dir)
        except Exception as exc:
            die(f"ALL-LANGS transcript fetch failed for {vid}: {exc}")
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
        vid = _validate_video_identity(vid, meta)
        payload = {
            "video_id": vid,
            "transcripts": all_transcripts,
            "metadata": meta or None,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    _, subfile = fetch_subtitle_files(vid, langs, work_dir=args.work_dir)
    segs = parse_json3(subfile)

    if not segs:
        die("Transcript file was empty — the track may have no text cues.")

    meta = {} if args.no_meta else fetch_metadata(vid)
    vid = _validate_video_identity(vid, meta)

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
