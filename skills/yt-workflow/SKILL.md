---
name: yt-workflow
description: Chain youtube → transcript → yt-script → yt-package → yt-seo → yt-viral → yt-retention. Use for "audit my channel", "why isn't this growing", "full channel review", "analyze competitor".
---

# yt-workflow: Channel Analysis Pipeline

## When to use

Any "audit my channel" / "why isn't this growing" / "full channel review" / "analyze competitor" request.

## The Pipeline (run in order, each feeds the next)

### Phase 1: Data Collection (youtube skill)

**Windows PowerShell** (run from repo root):
```powershell
python ..\youtube\scripts\ytdata.py sections "@handle"
python ..\youtube\scripts\ytdata.py channel "@handle" --limit 20 --with-duration
python ..\youtube\scripts\ytdata.py latest "@handle" --limit 10 --with-duration
python ..\youtube\scripts\ytdata.py home "@handle"
python ..\youtube\scripts\ytdata.py profile "@handle"
```

**Linux/macOS (bash/zsh):**
```bash
python ../youtube/scripts/ytdata.py sections "@handle"
python ../youtube/scripts/ytdata.py channel "@handle" --limit 20 --with-duration
python ../youtube/scripts/ytdata.py latest "@handle" --limit 10 --with-duration
python ../youtube/scripts/ytdata.py home "@handle"
python ../youtube/scripts/ytdata.py profile "@handle"
```

### Phase 2: Content Extraction (transcript skill)

**Windows PowerShell:**
```powershell
python ..\transcript\scripts\gettranscript.py "<video_id>" --format json --all-langs
```

**Linux/macOS:**
```bash
python ../transcript/scripts/gettranscript.py "<video_id>" --format json --all-langs
```

### Phase 3: Hook Analysis (yt-script skill)

```bash
# Score hooks from transcripts:
python ../yt-script/scripts/hookscore.py "<transcript_file.json>" --json
```

### Phase 4: Title/Thumbnail Analysis (yt-package skill)

```bash
# Score titles from channel data:
python ../yt-package/scripts/title.py --titles titles.txt --keyword "<keyword>"
```

### Phase 5: SEO / Keywords (youtube skill)

```bash
python ../youtube/scripts/ytdata.py keywords "niche" --patterns --json
python ../youtube/scripts/ytdata.py compete "keyword" --top 10 --json
python ../youtube/scripts/ytdata.py scorecard "<video_id>" --keyword "target" --json
python ../youtube/scripts/ytdata.py trends "seed idea" --days 30 --verbose --json
python ../youtube/scripts/ytdata.py gap "your seed" --competitor @theirhandle --json
```

### Phase 6: Outlier / Competitor Analysis (youtube skill)

```bash
python ../youtube/scripts/ytdata.py outliers "@handle" --min-ratio 2.0 --tab all --json
```

### Phase 7: Retention Analysis (yt-retention skill) — OPTIONAL but HIGH-LEVERAGE

```bash
# If user provides CSV export:
python ../yt-retention/scripts/retention.py retention.csv --json
```

**Agent behavior**: If no CSV provided, **ask the user to export it** — this phase is optional but high-leverage. Say: *"For retention analysis, I need the audience-retention CSV from YouTube Studio (Analytics → Engagement → Audience Retention → Download). Can you upload it? If not, I'll skip."*

---

## Pipeline Rules (Agent Must Follow)

1. **Never skip phases** — each phase produces required input for the next
2. **Pass JSON between phases** — use `--json` flags, parse output
3. **Fail fast** — if a phase fails, report what's missing and stop
4. **Cache intermediates** — save JSON to temp files, pass paths forward
5. **Handle missing data gracefully** — if optional phase data is missing (e.g., no retention CSV, no transcript for a video), note it in the output and continue. Don't halt the pipeline.
6. **Clean up downloaded artifacts** — yt-dlp may download thumbnail files (.webp, .jpg) and temp files. After each phase, delete any downloaded media files to avoid filling user disk space. Use `--no-thumbnails` flag when possible, or clean up `*.webp`, `*.jpg`, `*.mp4` files in the working directory after each command.

---

## ⚠️ Common Agent Errors (Avoid These)

| Error | Wrong | Correct |
|-------|-------|---------|
| Using TypeScript API | `await tools.youtube.channel(...)` | Use Python scripts: `python scripts/ytdata.py channel "@handle"` |
| PowerShell `&&` | `cd dir && python ...` | Use `;` or separate lines: `cd dir; python ...` |
| Bare UC ID | `python scripts/ytdata.py channel UC7YGYCm...` | Use `@handle`: `python scripts/ytdata.py channel "@handle"` |
| Missing subcommand | `python scripts/ytdata.py @handle` | Use subcommand: `python scripts/ytdata.py profile "@handle"` |
| Missing `--json` | Parsing text output | Always use `--json` for structured output |
| Missing `--all-langs` | `python ... gettranscript.py "id" --format json` | Use `--all-langs`: `python ... gettranscript.py "id" --format json --all-langs` |
| Missing `--json` on transcript | `python ... gettranscript.py "id"` | Use `--format json`: `python ... gettranscript.py "id" --format json --all-langs` |

---

## Required Inputs per Phase

| Phase | Skill | Input | Output |
|-------|-------|-------|--------|
| 1 | youtube | @handle | Channel data (sections, videos, home, profile) |
| 2 | transcript | Top 3 video IDs | Full transcripts (JSON + timestamps) |
| 3 | yt-script | Transcripts | Hook scores (0-100) per video |
| 4 | yt-package | Titles + hook scores | Title/thumbnail scores + briefs |
| 5 | yt-seo | Niche + target video | Keywords, competition scores, scorecards |
| 6 | yt-viral | Channel + niche | Outliers (views/subs ratio), competitor gaps |
| 7 | yt-retention | Studio CSV (optional) | Drop-off points, retention curves |

---

## Example Agent Prompt

```text
Run a full channel analysis on @Moments_Unscriptedorignal:

1. Run youtube skill: sections, channel, latest, home, profile
2. Get transcripts for top 3 videos by views (--all-langs)
3. Run yt-script hookscore on each transcript
4. Run yt-package title scoring on last 10 titles
5. Run yt-seo keywords for "space facts" niche
6. Run yt-seo compete for top keyword
7. Run yt-viral outliers on channel
8. Synthesize all into ONE fix, 3 working things, what NOT to do

Output: single biggest fix, 3 working things, what NOT to do.
```

---

## What Each Phase Produces

| Phase | Skill | Output |
|-------|-------|--------|
| 1 | youtube | Channel profile, videos list, sections, home tab data |
| 2 | transcript | Transcript JSON per video |
| 3 | yt-script | Hook score 0-100 per video |
| 4 | yt-package | Title score 0-100 per video |
| 5 | yt-seo | Keywords, competition score, SEO scorecard |
| 6 | yt-viral | Outlier videos (views/subs ratio), velocity |
| 7 | yt-retention | Retention curves, drop-off points (optional) |

The agent synthesizes all phases into: **one biggest fix + 3 things working + what NOT to do.**