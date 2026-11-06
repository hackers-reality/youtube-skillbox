---
name: yt-package
description: >-
  Write and lint the title and thumbnail for a YouTube video as one pairing,
  checking truncation, duplication and vagueness before publish. Use for
  "title ideas", "what should I call this", "thumbnail text", "my CTR is
  bad", packaging, or any request to rename or repackage an existing video.
---

**Pipeline Position:** Phase 4 — Title/Thumbnail Audit
**Inputs:** Channel titles from youtube skill; hook scores from yt-script
**Outputs:** Title scores (heuristic), thumbnail briefs → feeds yt-seo, yt-workflow (agent synthesizes)
**Triggers:** title ideas, thumbnail text, packaging, CTR is bad



# 

## Prerequisites

`yt-dlp` installed: `python -m pip install --user -U yt-dlp`. Uses the shared data module at `../youtube/scripts/ytdata.py` (relative to this SKILL.md). **Ensure `youtube/scripts/ytdata.py` exists alongside this skill** (copy `scripts/` when installing).

# yt-package

The title and the thumbnail are ONE unit. Writing them separately is why most packaging fails: the
thumbnail repeats the title, and half the click surface says the same thing twice.

```bash
python3 title.py --title "..." --thumb "AI RAN IT"
python3 title.py titles.txt            # one per line, ranked
```

## Before you write

1. Read `~/.claude/youtube/voice.md` if it exists. That is the user's voice profile: how they talk
   on camera, the words they never use, who they are talking to, what they will not claim. If it
   does not exist, ask for **three of their own videos**, read or transcribe them, infer the voice,
   and write the file. A script in the wrong voice is worse than no script, because they have to
   read it out loud.
2. Never invent a number, a result or a source. If a figure would strengthen it and you do not have
   one, ask for it or write the line without it.

## Honesty rules (non-negotiable)

- **Thumbnail text is not the thumbnail image.** `title.py` scores *text only*. You may never claim to have "checked the contrast", "seen the face", "evaluated the actual thumbnail", or to have derived anything from the pixels when only text was supplied. If no thumbnail image was provided, say **"thumbnail not evaluated — text only"** and score only the text.
- **Scores are heuristics, not forecasts.** A 47/100 title score is a signal about the title text, not a prediction of CTR, ranking, impressions or views. Never write "this will get X% CTR" or "YouTube will rank this".
- **Never present a heuristic as an outcome.** Say "heuristic score: 47/100 (title text only)" or "thumbnail not evaluated".
- **Verdicts must match the tool.** SHIP/REVISE/REWORK comes from the tool, not from your gut. Quote the exact counts the tool returned (e.g., 9 REWORK out of 10 title entries — never "all 18" when that is not what the output said).
- **No invented thumbnail copy.** If the user did not give you thumbnail text, do not invent it — ask, or score without one.

## Rules the tool enforces, and why

- **60 characters** is where desktop search truncates, **40** is a mobile home feed. Both are
  reported because they fail differently: a desktop cut loses the tail, a mobile cut can lose the
  subject.
- **The thumbnail must not repeat the title.** Different words, same promise.
- **Three words maximum on the thumbnail.** At feed size a fourth word is a grey smear.
- **A number, a name or a date** beats every adjective available to you.
- **Two all-caps words is the ceiling** before a title reads as spam.

## Write ten, keep two

Generate ten titles, run them all through `title.py`, show the user the top three with their scores
and the specific issue on each. For the winner, write the thumbnail brief: the expression, the
framing, the three words, and what the background has to do to hold contrast at feed size.

## The gate

Nothing here publishes. This skill writes and you publish. Every output ends in a block the user
copies, and the last line of every run is the question: **ship it, or change it?**


---
> **Artifact destination applies.** If this skill writes any file (manifest, transcript, CSV, report, log, temp output), the user-selected artifact destination governs it — see yt-guide "Artifact Destination Policy". Ask first if not established; absolute paths only; everything inside that directory; never Temp/Desktop/Downloads/cwd; never overwrite without permission; verify and report artifact paths.
