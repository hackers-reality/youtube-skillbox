---
name: transcript
description: "Use when the spoken content, captions, or subtitles of a YouTube video are needed — even if not explicitly requested: pasted video links or IDs, requests to summarize, quote, transcribe, translate, fact-check, or extract anything from a video; convert video to text; accessibility needs, deaf/HoH use cases, reading along, language learning, or content review. Also use when a user shares a video URL and wants to know what it says, or for research/learning where a video is the source. Not for uploads or account management."
---

# Transcript

**Pipeline Position:** Phase 2 — Content Extraction
**Inputs:** Video IDs from youtube skill (Phase 1)
**Outputs:** Full transcript JSON (text, timestamps, metadata) → feeds yt-script (hook scoring), yt-seo (spoken keywords), yt-audit (retention analysis)

Extract the spoken text of any YouTube video — **free, no API key, no credits** — using local `yt-dlp`.

## Prerequisites

`yt-dlp` must be installed. It is already installed on this machine; if missing, run:

```bash
python -m pip install --user -U yt-dlp
```

Run it as a module (`python -m yt_dlp`) — the `yt-dlp` exe may not be on PATH. The helper script below already does this.

## How to use

A helper script lives at `scripts/gettranscript.py` (relative to this SKILL.md). Invoke it with `python`:

```bash
python scripts/gettranscript.py "<url-or-id>"                    # clean text (default)
python scripts/gettranscript.py "<url-or-id>" --format stamped   # [MM:SS] per line
python scripts/gettranscript.py "<url-or-id>" --format json      # structured + metadata
python scripts/gettranscript.py "<url-or-id>" --lang es,es-419   # language priority list
python scripts/gettranscript.py "<url-or-id>" --all-langs        # fetch ALL available tracks
python scripts/gettranscript.py "<url-or-id>" --no-meta          # skip metadata (faster)
```

The script accepts a full URL, `youtu.be/ID`, `youtube.com/shorts/ID`, or a bare 11-char ID.

## Which format to pick

| Need | Format |
| ---- | ------ |
| Summarize, translate, fact-check, general reading | `text` (default) |
| Quote a specific moment / cite a timestamp | `stamped` |
| Programmatic use, exact `start`/`duration` per line | `json` |

## Output details

- **text** — one continuous string of spoken words, timestamps stripped. Best for feeding to a summarizer or translator.
- **stamped** — one `[MM:SS] text` line per caption cue. Good for pointing at "at 4:12 he says X."
- **json** — shape:
  ```json
  {
    "video_id": "dQw4w9WgXcQ",
    "language": "en-orig",
    "generated": false,
    "segment_count": 52,
    "metadata": { "title": "...", "author_name": "...", "duration_seconds": 213, "view_count": 1832037840, "...": "..." },
    "transcript": [ { "text": "...", "start": 18.0, "duration": 2.5 } ]
  }
  ```
  `generated: false` = human captions; `true` = YouTube auto-captions (slightly less accurate).

## Language

`--lang` is a **priority list**, first available wins. Default is `en`. For a Spanish video use `--lang es,es-419,en`. To translate, fetch then translate the text yourself — this tool returns the caption track as-is, it does not machine-translate.

**Multi-language support**: Use `--all-langs` to fetch **every available subtitle track** (manual + auto-generated). Returns a JSON array of transcripts with language metadata. Use this when:
- Video may have non-English original language (e.g., Marathi `mr-orig`)
- Auto-translated English is poor quality
- You want to compare translations for accuracy

## Behavior & limits

- Prefers manual captions, falls back to auto-generated.
- **No credits, no rate limit for normal use** — but YouTube may throttle (HTTP 429) if you hammer it; add a small delay between many videos.
- Fails (with a clear message) if: captions disabled, private, age-restricted, or none of your requested languages exist.
- Speed: a few seconds per video (local tool startup). Fine for occasional use; for bulk, expect ~1–2s each.

## When you need MORE than transcripts

This skill only pulls the spoken text. For **search, channel browsing, playlists, community posts, or rich metadata**, use the `youtube` skill instead — it covers everything else (search, channels, playlists, metadata, community posts, home sections) free via yt-dlp + raw page scraping, and it needs no API key either.

## Tips

- Long video? Summarize the key points first, then offer the full transcript on request.
- Use `stamped` when the user asks "where does he say X" or wants timestamps.
- If a very new video returns nothing, auto-captions may not be generated yet — tell the user.
