---
name: yt-retention
description: >-
  Read a YouTube Studio audience-retention export and find where viewers
  actually leave, then say what to change. Use for "why do people stop
  watching", "my retention is bad", a pasted retention chart or CSV, or "fix
  my pacing".
---

**Pipeline Position:** Phase 7 — Retention Analysis (optional)
**Inputs:** YouTube Studio retention CSV export from user
**Outputs:** Drop-off points, retention curves → feeds yt-workflow (agent synthesizes)
**Triggers:** why do people stop watching, retention is bad, fix my pacing



# 

## Prerequisites

`yt-dlp` installed: `python -m pip install --user -U yt-dlp`. Uses the shared data module at `../youtube/scripts/ytdata.py` (relative to this SKILL.md). **Ensure `youtube/scripts/ytdata.py` exists alongside this skill** (copy `scripts/` when installing).

# yt-retention

The retention graph is the only honest feedback YouTube gives you. Almost nobody exports it.

```bash
python3 retention.py retention.csv --duration 600
python3 retention.py retention.csv --transcript transcript.srt
python3 retention.py /path/to/Studio-export/ --dir          # inventory EVERY CSV, not just All.csv
```

Getting the export: Studio -> a video -> Analytics -> Engagement -> the audience-retention chart ->
the download icon -> "Audience retention". **YouTube Studio's export is a ZIP of multiple CSVs** — not a single file. Do not analyze `All.csv` alone; run the `--dir` inventory first and read every CSV it finds.

## Multi-CSV exports — what each file actually measures

| File | Measures | You must NOT claim |
|------|----------|--------------------|
| `All.csv` | Absolute retention, all viewers | "X% of viewers are/were..." |
| `Subscribers and non-subscribers.csv` | Segmented retention curves (sub vs non-sub) | "% of viewers who are subscribers" |
| `New and returning viewers.csv` | Segmented retention curves (new vs returning) | "% of viewers who are new vs returning" |
| `New, casual and regular viewers.csv` | Segmented retention curves (watch frequency) | audience-size proportions |
| `Organic and paid traffic.csv` | Segmented retention by traffic source | overall organic vs paid share |
| `Organic.csv` | Retention, organic traffic only | any paid comparison |
| `Skippable video ad.csv` / `Video discovery ad.csv` | Retention of ad views | organic performance |
| `Detailed activity.csv` | Per-position started/stopped/moments-seen counts | proportions of audience |

**Rule: none of these CSVs proves audience proportions, traffic shares or demographics unless the columns explicitly contain those measures.** Label findings as MEASURED / INFERRED / HYPOTHESIS. Values >100% in absolute retention mean rewatches/loops, not ">100% of the audience".

**Agent behavior**: If no CSV is provided, **ask the user to export and upload it** — this phase is optional but high-leverage. Say: *"For retention analysis, I need the audience-retention CSV from YouTube Studio (Analytics → Engagement → Audience Retention → Download). It's a ZIP of several CSVs — upload it all if possible. If not, I'll skip to the final synthesis."*

## Three different problems

- **HOOK LEAK** - what is lost in the first 30 seconds. Under 25% is healthy. This is always the
  first thing to fix and it is always the first fifteen seconds of script, never the edit.
- **CLIFFS** - single steep drops. A cliff is a moment: a topic change with no signposting, a
  sponsor read, a long setup. With `--transcript` the tool prints what was being said there, which
  is what makes the report actionable instead of interesting.
- **SLIDE** - the steady bleed across the middle. A flat slide is pacing. The fix is cutting, not
  rewriting.

## What to hand back

Name the single biggest leak and one change for it. Not a list of five. Then, only if asked, the
rest. And if the hook leak is healthy and the slide is flat, say the video is fine and the problem
is packaging - send them to `/yt-package`.

## The gate

Nothing here publishes. This skill writes and you publish. Every output ends in a block the user
copies, and the last line of every run is the question: **ship it, or change it?**


---
> **Artifact destination applies.** If this skill writes any file (manifest, transcript, CSV, report, log, temp output), the user-selected artifact destination governs it — see yt-guide "Artifact Destination Policy". Ask first if not established; absolute paths only; everything inside that directory; never Temp/Desktop/Downloads/cwd; never overwrite without permission; verify and report artifact paths.
