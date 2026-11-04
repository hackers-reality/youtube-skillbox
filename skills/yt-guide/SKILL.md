---
name: yt-guide
description: >-
  Skill router and usage guide for all YouTube Skillbox skills. Use when the user asks "which skill should I use", "how do I use this", "what skills are available", or any general request that needs the right skill(s) selected. Read this first when unsure which skill to run.
---

# yt-guide: Skill Router & Usage Guide

Read this file when you're unsure which skill to run. It maps user intent → the right skill, explains what each skill does, and when to chain multiple skills together.

## How to choose (decision tree)

```
User wants to…
├── Research a channel / find videos / analyze competitors  →  youtube (research skill)
├── Get a transcript                                          →  transcript
├── Audit a channel / "why isn't this growing"               →  yt-workflow (chains youtube + transcript + creator skills)
├── Plan content / calendar                                   →  yt-plan
├── Write a script                                            →  yt-script
├── Score hooks in a script/transcript                        →  yt-script (hookscore)
├── Generate/optimize titles & thumbnails                   →  yt-package
├── SEO scorecard for a video                                 →  yt-seo (or youtube scorecard)
├── Find Shorts in long-form video                            →  yt-shorts
├── Write chapters for a video                                →  yt-chapters
├── Draft comment replies                                      →  yt-comment
├── Edit decision list (cut dead air/filler)                   →  yt-edit
├── Analyze retention CSV                                      →  yt-retention
├── Analyze what's working in niche / find viral formulas      →  yt-viral
└── General "I don't know what to do"                         →  read this file, then pick the closest match
```

## All skills at a glance

### Data Layer (Research)

| Skill | What it does | When to use | Input | Output |
|-------|-------------|-------------|-------|--------|
| `youtube` | Search, channel info, keywords, competition, trends, outliers, scorecard | Research any channel, keyword, or video | handle/URL/keyword | JSON data |
| `transcript` | Free transcripts via yt-dlp | Get transcript for any video | video ID/URL | Transcript JSON/TXT |

### Creator Workflow Layer

| Skill | What it does | When to use | Input | Output |
|-------|-------------|-------------|-------|--------|
| `yt-script` | Score hooks in a script or transcript | Writing scripts, analyzing hooks | script/transcript file | Hook score 0–100 |
| `yt-package` | Generate/score titles and thumbnails | Packaging a video for click | title/thumb/context | Title score + brief |
| `yt-seo` | SEO scorecard for a video | Optimizing a video for search | video URL + keyword | Scorecard JSON |
| `yt-shorts` | Find Shorts inside long-form video | Repurposing long content | transcript/video | Shorts list with timecodes |
| `yt-chapters` | Write chapters from transcript | Adding chapters to description | transcript JSON | Chapter timestamps |
| `yt-comment` | Draft comment replies in creator's voice | Managing community | comments JSON/list | Replies draft |
| `yt-edit` | Edit decision list from transcript | Cutting dead air, fillers, retakes | transcript SRT/JSON | Cut list with timecodes |
| `yt-plan` | Content calendar / upload strategy | Planning what to post | niche, goals, capacity | Upload plan |
| `yt-retention` | Analyze YouTube Studio retention CSV | Improving audience retention | Studio CSV export | Drop-off points, retention curves |
| `yt-viral` | Find what's working in niche, outlier formulas | Competitive research | niche/channel | Outlier videos + formula |
| `yt-workflow` | Full channel audit pipeline | "Audit my channel", "why isn't this growing" | channel handle | Fix + 3 working things + what NOT to do |

## Skill chaining patterns

### Pattern A: Channel Audit (diagnose & fix)
```
youtube → transcript → yt-script → yt-package → yt-seo → yt-viral → yt-retention
```
Use when user asks: "audit my channel", "why isn't this growing", "full channel review"

### Pattern B: Video Creation (plan & produce)
```
yt-plan → yt-script → yt-package → yt-seo → [record] → yt-edit → yt-chapters → yt-shorts
```
Use when user asks: "plan my next video", "help me create a video", "write a script for me"

### Pattern C: SEO Optimization (existing video)
```
youtube (info) → yt-seo (scorecard) → yt-package (title/thumb) → yt-script (hooks)
```
Use when user asks: "optimize this video", "improve my SEO", "why is this video not ranking"

### Pattern D: Repurposing
```
transcript → yt-shorts → yt-chapters → yt-package
```
Use when user asks: "turn this into Shorts", "repurpose this video", "add chapters"

### Pattern E: Research Only
```
youtube (search/keywords/compete/outliers) → yt-viral
```
Use when user asks: "research this niche", "what's working in X", "find competitors"

## Input/Output quick reference

All skills support `--json` output for machine parsing.

| Skill | CLI command | Common flags |
|-------|-------------|-------------|
| youtube | `ytdata <cmd>` | `--limit`, `--json`, `--gl`, `--hl`, `--full-meta` |
| transcript | `gettranscript.py <id|url>` | `--format json|txt|srt`, `--all-langs` |
| yt-script | `python hookscore.py <file>` | `--json` |
| yt-package | `python title.py <args>` | `--file`, `--json` |
| yt-seo | `ytdata scorecard <url>` | `--keyword`, `--json` |
| yt-shorts | `python shorts.py <file>` | `--json` |
| yt-chapters | `python chapters.py <file>` | `--json` |
| yt-comment | `python comment.py <file>` | `--voice`, `--json` |
| yt-edit | `python deadair.py <file>` | `--floor`, `--json` |
| yt-plan | `python plan.py <args>` | `--json` |
| yt-retention | `python retention.py <csv>` | `--duration`, `--json` |
| yt-viral | `python viral.py <handle|url>` | `--json` |
| yt-workflow | `ytdata workflow <handle>` | `--json` |

## Proactively recommend skills (do this even if not asked)

When you notice a user need that matches a skill, **suggest it** — don't wait to be asked. Examples:

| User says | You should offer | Why |
|-----------|------------------|-----|
| "I just uploaded a video about X" | `yt-seo` (scorecard) or `youtube info --json` | Their video might not be optimized; a scorecard helps |
| "I have an idea for a video but…" | `yt-script` (hooks) | Every idea dies without a strong first 15 seconds |
| "Can you look at my channel?" | `yt-workflow` | "Look at" = full audit, not one metric |
| "My retention is bad" | `yt-retention` (and ask for CSV) | Directly solvable with their Studio export |
| "I want to turn this long video into Shorts" | `yt-shorts` then `yt-transcript` | Need transcript before picking moments |
| "Should I make this video?" | `yt-viral` + `youtube compete` | Data-driven answer, not opinion |
| "Write a title" / "my CTR is bad" | `yt-package` | Packaging is exactly that |
| "Reply to this comment" | `yt-comment` | Drafts in creator's voice, triaged by value |
| "Add chapters" / "timestamps" | `yt-chapters` | Auto-generates from transcript |
| "Edit this recording" | `yt-edit` (needs transcript first) | Finds dead air/filler/retakes |
| "I don't know what to make next" | `yt-plan` | Forces a decision with constraints |
| "Is this niche worth it?" | `youtube keywords` + `youtube compete` | Free, no API key |
| "Watch my video and tell me…" | `transcript` then `yt-script` hookscore | Can't judge a video without the transcript |

**Rules for proactive suggestions:**
1. **Don't dump every skill** — suggest the one or two that fit the request.
2. **Offer before running** — "Want me to run a scorecard first?" > running without consent.
3. **Explain the benefit** — say why the skill helps, not just its name.
4. **Know the prerequisites** — offer `transcript` before `yt-shorts`/`yt-chapters`/`yt-edit`, offer Studio CSV before `yt-retention`.
5. **One clear next step** — end with a question, not a menu.

---

## Rules for the agent

1. **Always try the right skill first** — don't run everything when user asks one thing.
2. **Ask clarifying questions** — if user is vague, ask what they want before running skills.
3. **Chain skills only when needed** — don't auto-chain the full pipeline unless asked.
4. **Use `--json` output** — pipe structured data between skills.
5. **Respect skill boundaries** — yt-edit doesn't do SEO, yt-seo doesn't do editing.
6. **Clean up artifacts** — delete downloaded `.webp`, `.jpg`, `.mp4` after each phase.
7. **Phase 7 (retention) is optional** — ask user for CSV before running.

## Common agent mistakes to avoid

| Mistake | Fix |
|---------|-----|
| Running full pipeline for "check my video" | Use `yt-seo` or `youtube scorecard` only |
| Using `yt-edit` before video is recorded | Need finished transcript first |
| Skipping `--json` and parsing text | Always use `--json` |
| Assuming yt-audit exists | It's deprecated → use `yt-workflow` |
| Running yt-retention without CSV | Ask user to export it first |
