---
name: transcript
description: "Use when the spoken content, captions, or subtitles of a YouTube video are needed — even if not explicitly requested: pasted video links or IDs, requests to summarize, quote, transcribe, translate, fact-check, or extract anything from a video; convert video to text; accessibility needs, deaf/HoH use cases, reading along, language learning, or content review. Also use when a user shares a video URL and wants to know what it says, or for research/learning where a video is the source. Not for uploads or account management."
---

# Transcript

**Pipeline Position:** Phase 2 — Content Extraction
**Inputs:** Video IDs from youtube skill (Phase 1)
**Outputs:** Full transcript JSON (text, timestamps, metadata) → feeds yt-script (hook scoring), yt-seo (spoken keywords), yt-workflow (agent synthesizes)

Extract the spoken text of any YouTube video — **free, no API key, no credits** — using local `yt-dlp`.

## Prerequisites

`yt-dlp` must be installed. It is already installed on this machine; if missing, run:

```bash
python -m pip install --user -U yt-dlp
```

Run it as a module (`python -m yt_dlp`) — the `yt-dlp` exe may not be on PATH. The helper script below already does this.

## How to use

A helper script lives at `scripts/gettranscript.py` (relative to this SKILL.md). **Run from repo root.**

### Windows PowerShell (use `;` not `&&`):
```powershell
python scripts/gettranscript.py "<url-or-id>" --format json
python scripts/gettranscript.py "<url-or-id>" --format json --original-lang
python scripts/gettranscript.py "<url-or-id>" --lang mr,en
python scripts/gettranscript.py "<url-or-id>" --format json --original-lang --work-dir "<artifact-destination>"
python scripts/gettranscript.py "<url-or-id>" --format json --all-langs --work-dir "<artifact-destination>"
```

### Linux/macOS (bash/zsh):
```bash
python scripts/gettranscript.py "<url-or-id>" --format json
python scripts/gettranscript.py "<url-or-id>" --format json --original-lang
python scripts/gettranscript.py "<url-or-id>" --lang mr,en
python scripts/gettranscript.py "<url-or-id>" --format json --original-lang --work-dir "<artifact-destination>"
python scripts/gettranscript.py "<url-or-id>" --format json --all-langs --work-dir "<artifact-destination>"
```

### `--original-lang` (preferred) — so the CLI documentation is honest:
- Detects the original spoken language (preferring a manual `*-orig` track).
- If original == English, fetches **English only**.
- Otherwise fetches **original + English** — two requests max.
- Faster and more reliable than `--all-langs`, which bursts every auto-translated track (~150 langs) and reliably throttles (HTTP 429 on tracks like `ab`).
- If enumeration/detection fails, exits non-zero — never silently falls back to a single language.

### Input formats accepted:
- Full URL: `https://www.youtube.com/watch?v=9NDb3RH9N7M`
- Short URL: `https://youtu.be/9NDb3RH9N7M`
- Shorts URL: `https://www.youtube.com/shorts/9NDb3RH9N7M`
- Bare ID: `9NDb3RH9N7M`

### Critical Syntax Rules:
- **Use `--json`** for structured output (parsing text is fragile)
- **Use `--original-lang`** to fetch the original language + English only (fastest, avoids the `--all-langs` 429 burst)
- **Use `--all-langs`** only when you explicitly need EVERY subtitle track (manual + auto) — expect 429 throttle on obscure auto tracks like `ab`; failure keeps exit non-zero, never silently downgrades
- **Windows: use `;` not `&&`** for command chaining in PowerShell
- **Run from repo root** — script uses relative paths

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

**Original-language default**: Use `--original-lang` to fetch **original + English only**. It detects the original spoken language (manual `*-orig` preferred), never downloads the 150 fake/auto tracks, and never causes a 429 burst. This is what the workflow uses by default.

**Multi-language support**: Use `--all-langs` ONLY when you genuinely need **every available subtitle track** (manual + auto-generated). Returns a JSON array of transcripts with language metadata. Use this when:
- Video has many distinct legitimate original captions you need (rare)
- You want to compare translations for accuracy
- `--original-lang` failed allita or the user explicitly asks for all

`--all-langs` and other CLI flags are always parsed as options, never as video IDs. If an explicitly requested option cannot be satisfied, the script exits non-zero and reports it — it does **not** silently downgrade to a default-language transcript.

## Behavior & limits

- Prefers manual captions, falls back to auto-generated.
- **No credits, no user-supplied YouTube Data API key** — but YouTube may throttle (HTTP 429) if you hammer it; add a small delay between many videos.
- Fails (with a clear message) if: captions disabled, private, age-restricted, or none of your requested languages exist.
- Speed: a few seconds per video (local tool startup). Fine for occasional use; for bulk, expect ~1–2s each.

## When you need MORE than transcripts

This skill only pulls the spoken text. For **search, channel browsing, playlists, community posts, or rich metadata**, use the `youtube` skill instead — it covers everything else (search, channels, playlists, metadata, community posts, home sections) free via yt-dlp + raw page scraping, and it needs no API key either.

## Tips

- Long video? Summarize the key points first, then offer the full transcript on request.
- Use `stamped` when the user asks "where does he say X" or wants timestamps.
- If a very new video returns nothing, auto-captions may not be generated yet — tell the user.


---
> **Artifact destination applies.** If this skill writes any file (manifest, transcript, CSV, report, log, temp output), the user-selected artifact destination governs it — see yt-guide "Artifact Destination Policy". Ask first if not established; absolute paths only; everything inside that directory; never Temp/Desktop/Downloads/cwd; never overwrite without permission; verify and report artifact paths.
