---
name: yt-comment
description: >-
  Draft replies to YouTube comments in the creator's voice, triaged by which
  ones are worth answering. Use for "reply to my comments", "handle the
  comment section", "someone asked X", or a pasted comment thread.
---**Pipeline Position:** Post-Publish — Community Management
**Inputs:** Channel handle + comment threads from youtube skill
**Outputs:** Draft replies in creator voice → feeds community management
**Triggers:** reply to comments, handle comment section



# 

## Prerequisites

`yt-dlp` installed: `python -m pip install --user -U yt-dlp`. Uses the shared data module at `../youtube/scripts/ytdata.py` (relative to this SKILL.md). **Ensure `youtube/scripts/ytdata.py` exists alongside this skill** (copy `scripts/` when installing).

# yt-comment

The comment section is a retention surface, not a chore. Replies in the first few hours are what
decide whether a thread becomes a conversation other people read.

## Before you write

1. Read `~/.claude/youtube/voice.md` if it exists. That is the user's voice profile: how they talk
   on camera, the words they never use, who they are talking to, what they will not claim. If it
   does not exist, ask for **three of their own videos**, read or transcribe them, infer the voice,
   and write the file. A script in the wrong voice is worse than no script, because they have to
   read it out loud.
2. Never invent a number, a result or a source. If a figure would strengthen it and you do not have
   one, ask for it or write the line without it.

## Triage first, always

Sort what the user pastes into four piles and say how many are in each before writing anything:

1. **Questions** - answer them. These are your next video's topics, so note the repeats.
2. **Corrections** - if they are right, say so plainly and thank them. Never argue a fact you
   cannot check.
3. **Praise** - reply to a few, briefly, with something specific from their comment. A wall of
   identical "thank you!" replies reads as automated because it is.
4. **Bait** - do not reply. Say so and move on. Never write a comeback, however deserved.

## Writing the reply

- Under 30 words. A long reply in a comment thread is a blog post nobody asked for.
- Answer the actual question in the first sentence.
- One question back, only when it is real.
- No emoji unless the user's own replies use them. Check their voice file.
- Never promise a video you have not agreed to make.

## The heart and the pin

Say which ONE comment to pin and why. Pin the question the most people also have, not the nicest
one. Heart generously - it costs nothing and it is visible.

## The gate

Nothing here publishes. This skill writes and you publish. Every output ends in a block the user
copies, and the last line of every run is the question: **ship it, or change it?**


---
> **Artifact destination applies.** If this skill writes any file (manifest, transcript, CSV, report, log, temp output), the user-selected artifact destination governs it — see yt-guide "Artifact Destination Policy". Ask first if not established; absolute paths only; everything inside that directory; never Temp/Desktop/Downloads/cwd; never overwrite without permission; verify and report artifact paths.
