---
name: yt-workflow
description: Chain youtube → transcript → yt-script → yt-package → yt-seo → yt-viral → yt-retention. Use for "audit my channel", "why isn't this growing", "full channel review", "analyze competitor".
---

# yt-workflow: Channel Analysis Pipeline

## ⚡ Quick Start: Installed CLI

After installing the package (`pip install -e .`), the **`ytdata`** command is available globally. Use it directly instead of `python skills/youtube/scripts/ytdata.py`:

```bash
# Before (repo-root relative paths)
python skills/youtube/scripts/ytdata.py sections "@handle"

# After install (works from anywhere)
ytdata sections "@handle"
ytdata channel "@handle" --limit 20 --with-duration
ytdata latest "@handle" --limit 10 --with-duration
ytdata home "@handle"
ytdata profile "@handle"
ytdata keywords "niche" --patterns --json
ytdata compete "keyword" --top 10 --json
ytdata scorecard "<video_id>" --keyword "target" --json
ytdata outliers "@handle" --min-ratio 2.0 --tab all --json
```

> **Note:** The examples below use `python skills/youtube/scripts/ytdata.py` for repo-root execution. After `pip install -e .`, prefer the `ytdata` command — it works from any directory.

> **Unsure which skill to use?** Read `skills/yt-guide/SKILL.md` — it's a decision tree that maps user intent to the right skill and explains all skills, when to use each, and how to chain them.

## When to use

Any "audit my channel" / "why isn't this growing" / "full channel review" / "analyze competitor" request.

## The Pipeline (run in order, each feeds the next)

### Phase 1: Data Collection (youtube skill)

**Windows PowerShell** (run from repo root):
```powershell
python skills\youtube\scripts\ytdata.py sections "@handle"
python skills\youtube\scripts\ytdata.py channel "@handle" --limit 20 --with-duration
python skills\youtube\scripts\ytdata.py latest "@handle" --limit 10 --with-duration
python skills\youtube\scripts\ytdata.py home "@handle"
python skills\youtube\scripts\ytdata.py profile "@handle"
```

**Linux/macOS (bash/zsh):**
```bash
python skills/youtube/scripts/ytdata.py sections "@handle"
python skills/youtube/scripts/ytdata.py channel "@handle" --limit 20 --with-duration
python skills/youtube/scripts\ytdata.py latest "@handle" --limit 10 --with-duration
python skills/youtube/scripts\ytdata.py home "@handle"
python skills/youtube/scripts\ytdata.py profile "@handle"
```

### Phase 2: Content Extraction (transcript skill)

**Windows PowerShell:**
```powershell
python skills\transcript\scripts\gettranscript.py "<video_id>" --format json --all-langs
```

**Linux/macOS:**
```bash
python skills/transcript/scripts/gettranscript.py "<video_id>" --format json --all-langs
```

### Phase 3: Hook Analysis (yt-script skill)

```bash
# Score hooks from transcripts:
python skills/yt-script/scripts/hookscore.py "<transcript_file.json>" --json
```

### Phase 4: Title/Thumbnail Analysis (yt-package skill)

```bash
# Score titles from channel data (using --file with JSON):
python skills/yt-package/scripts/title.py --file titles.json --json
```

Example `titles.json`:
```json
{
  "titles": [
    {
      "title": "Example YouTube title",
      "keyword": "example keyword",
      "thumb": "WATCH THIS"
    }
  ]
}
```

### Phase 5: SEO / Keywords (youtube skill)

```bash
python skills/youtube/scripts/ytdata.py keywords "niche" --patterns --json
python skills/youtube/scripts/ytdata.py compete "keyword" --top 10 --json
python skills/youtube/scripts/ytdata.py scorecard "<video_id>" --keyword "target" --json
python skills/youtube/scripts/ytdata.py trends "seed idea" --days 30 --verbose --json
python skills/youtube/scripts/ytdata.py gap "your seed" --competitor @theirhandle --json
```

### Phase 6: Outlier / Competitor Analysis (youtube skill)

```bash
python skills/youtube/scripts/ytdata.py outliers "@handle" --min-ratio 2.0 --tab all --json
```

### Phase 7: Retention Analysis (yt-retention skill) — OPTIONAL but HIGH-LEVERAGE

```bash
# If user provides CSV export:
python skills/yt-retention/scripts/retention.py retention.csv --json
```

**Agent behavior**: If no CSV provided, **ask the user to export it** — this phase is optional but high-leverage. Say: *"For retention analysis, I need the audience-retention CSV from YouTube Studio (Analytics → Engagement → Audience Retention → Download). Can you upload it? If not, I'll skip."*

---

## Pipeline Rules (Agent Must Follow)

1. **Never skip required phases** — Phases 1–6 are required; each produces input for the next. Phase 7 (retention) is optional.
2. **Pass JSON between phases** — use `--json` flags, parse output.
3. **Fail fast on required phases** — if a required phase (1–6) fails, report what's missing and stop.
4. **Cache intermediates** — save JSON to temp files, pass paths forward.
5. **Handle missing data gracefully** — if optional phase data is missing (e.g., no retention CSV, no transcript for a video), note it in the output and continue. Don't halt the pipeline.
6. **Clean up downloaded artifacts** — yt-dlp may download thumbnail files (.webp, .jpg) and temp files. After each phase, delete any downloaded media files to avoid filling user disk space. Use `--no-thumbnails` flag when possible, or clean up `*.webp`, `*.jpg`, `*.mp4` files in the working directory after each command.

---

## ⚠️ Common Agent Errors (Avoid These)

| Error | Wrong | Correct |
|-------|-------|---------|
| Using TypeScript API | `await tools.youtube.channel(...)` | Use Python scripts: `python skills/youtube/scripts/ytdata.py channel "@handle"` |
| PowerShell `&&` | `cd dir && python ...` | Use `;` or separate lines: `cd dir; python ...` |
| Bare UC ID | `python skills/youtube/scripts/ytdata.py channel UC7YGYCm...` | Use `@handle`: `python skills/youtube/scripts/ytdata.py channel "@handle"` |
| Missing subcommand | `python skills/youtube/scripts/ytdata.py @handle` | Use subcommand: `python skills/youtube/scripts/ytdata.py profile "@handle"` |
| Missing `--json` | Parsing text output | Always use `--json` for structured output |
| Missing `--all-langs` | `python skills/transcript/scripts/gettranscript.py "id" --format json` | Use `--all-langs`: `python skills/transcript/scripts/gettranscript.py "id" --format json --all-langs` |
| Missing `--json` on transcript | `python skills/transcript/scripts/gettranscript.py "id"` | Use `--format json`: `python skills/transcript/scripts/gettranscript.py "id" --format json --all-langs` |
| PowerShell `Out-File -Encoding utf8` writes BOM | `... | Out-File -Encoding utf8 file.json` → then `json.load()` crashes with "Unexpected UTF-8 BOM" | Use Python to write files: `python -c "open(r'file.json','w',encoding='utf-8').write(out)"`, or read with BOM-tolerant code (scripts here already use `utf-8-sig`) |
| Windows cp1252 default encoding | `open(path)` without encoding → `UnicodeDecodeError` on emoji/smart quotes | Use `open(path, encoding='utf-8')` (or `utf-8-sig` for Windows-authored files) |
| **Truncating a file before reading it** | `open(p,'w').write(open(p,encoding='utf-8-sig').read())` — deletes the file! | Read first, then write: `data = open(p, encoding='utf-8-sig').read(); open(p,'w',encoding='utf-8').write(data)` |

---

## Required Inputs per Phase

| Phase | Skill | Input | Output |
|-------|-------|-------|--------|
| 1 | youtube | @handle | Channel data (sections, videos, home, profile) |
| 2 | transcript | Top 3 video IDs | Full transcripts (JSON + timestamps) |
| 3 | yt-script | Transcripts | Hook metrics (words/sec, questions, numbers, second-person, etc.) per video |
| 4 | yt-package | Titles + hook scores | Title/thumbnail scores + briefs |
| 5 | yt-seo | Niche + target video | Keywords, competition scores, scorecards |
| 6 | yt-viral | Channel + niche | Outliers (views/subs ratio), competitor gaps |
| 7 | yt-retention | Studio CSV (optional) | Drop-off points, retention curves |

---

## Example Agent Prompt

```text
Run a full channel analysis on @Moments_Unscriptedorignal:

1. Run youtube skill: sections, channel, latest, home, profile
   python skills/youtube/scripts/ytdata.py sections "@handle"
   python skills/youtube/scripts/ytdata.py channel "@handle" --limit 20 --with-duration
   python skills/youtube/scripts/ytdata.py latest "@handle" --limit 10 --with-duration
   python skills/youtube/scripts/ytdata.py home "@handle"
   python skills/youtube/scripts/ytdata.py profile "@handle"

2. Get transcripts for top 3 videos by views (--all-langs)
   python skills/transcript/scripts/gettranscript.py "<video_id>" --format json --all-langs

3. Run yt-script hookscore on each transcript
   python skills/yt-script/scripts/hookscore.py "<transcript_file.json>" --json

4. Run yt-package title scoring on last 10 titles
   python skills/yt-package/scripts/title.py --file titles.json --json

5. Run youtube skill keywords for "space facts" niche
   python skills/youtube/scripts/ytdata.py keywords "space facts" --patterns --json

6. Run youtube skill compete for top keyword
   python skills/youtube/scripts/ytdata.py compete "top keyword" --top 10 --json

7. Run youtube skill outliers on channel
   python skills/youtube/scripts/ytdata.py outliers "@handle" --min-ratio 2.0 --tab all --json

8. (Optional) Run yt-retention if user provides Studio CSV
   python skills/yt-retention/scripts/retention.py retention.csv --json --duration <seconds>

9. Synthesize all into ONE fix, 3 working things, what NOT to do

Output: single biggest fix, 3 working things, what NOT to do.
```

---

## What Each Phase Produces

| Phase | Skill | Output |
|-------|-------|--------|
| 1 | youtube | Channel profile, videos list, sections, home tab data |
| 2 | transcript | Transcript JSON per video |
| 3 | yt-script | Hook metrics per video (raw stats, not a 0-100 score) |
| 4 | yt-package | Title score 0-100 per video |
| 5 | yt-seo | Keywords, competition score, SEO scorecard |
| 6 | yt-viral | Outlier videos (views/subs ratio), velocity |
| 7 | yt-retention | Retention curves, drop-off points (optional) |

The agent synthesizes all phases into: **one biggest fix + 3 things working + what NOT to do.**