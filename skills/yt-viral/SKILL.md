---
name: yt-viral
description: >-
  Find what is actually working in the user's niche on YouTube and rank it
  by how far each video beat its own channel, then name the formula. Use for
  "what's working right now", "find viral videos in my niche", "why did this
  blow up", competitor research, or a swipe file.
---**Pipeline Position:** Phase 6 — Outlier / Competitor Analysis
**Inputs:** Channel handle from user; niche from youtube skill
**Outputs:** Outliers (views/subs ratio), competitor analysis → feeds yt-workflow (agent synthesizes)
**Triggers:** what's working in niche, find viral videos, why did this blow up


# yt-viral

Raw view counts rank channel size, not ideas. This ranks by **multiple over each channel's own
median**, which is the only version of the question that is about the video.

```bash
python3 swipe.py collected.json --min 2.0
```

## Collecting the input

You need at least **four videos per channel** or a median means nothing, and the tool will skip the
channel and tell you it did. Collect them however the user prefers - `yt-dlp --flat-playlist -J`
against a channel URL is the fastest, the public page works, a manual list works.

```json
[{"channel":"...","title":"...","views":412000,"url":"...","duration":613}]
```

**Read, do not scrape.** Public listings only, never a logged-in session, never the user's own
account credentials.

## Reading the output

The multiple is the signal. The formula line is a judgement about the TITLE, matched against
[the 21 formulas](../yt-script/hooks.json) - it is not a claim about why the video worked, and you
should say so when you present it.

What to hand back: the top five with their multiples, the formula each used, and the ONE structural
thing they share. Then the harder line - which of those the user could actually make this week, in
their voice, with what they have.

## ⚠️ Performance Note

This skill's `viral.py` script uses yt-dlp to fetch channel metadata and individual video details,
which can be slow for large channels (one yt-dlp call per video). For faster outlier detection
that scans both videos and shorts tabs in a single pass, prefer the **youtube skill's `outliers` subcommand**:

```bash
python skills/youtube/scripts/ytdata.py outliers "@handle" --min-ratio 2.0 --tab all --json
```

This uses flat-playlist (which includes view_count) and fast Innertube API for subscriber counts,
making it significantly faster for large channels.

## The gate

Nothing here publishes. This skill writes and you publish. Every output ends in a block the user
copies, and the last line of every run is the question: **ship it, or change it?**

---
> **Artifact destination applies.** If this skill writes any file (manifest, transcript, CSV, report, log, temp output), the user-selected artifact destination governs it — see yt-guide "Artifact Destination Policy". Ask first if not established; absolute paths only; everything inside that directory; never Temp/Desktop/Downloads/cwd; never overwrite without permission; verify and report artifact paths.
