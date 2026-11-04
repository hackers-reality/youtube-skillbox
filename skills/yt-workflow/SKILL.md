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

## When to use

Any "audit my channel" / "why isn't this growing" / "full channel review" / "analyze competitor" request.

## Phase 0 — CONSULT yt-guide FIRST (mandatory)

Before running anything, **read `skills/yt-guide/SKILL.md`** and use its decision tree to select this chain. Do not "vibe-audit" — the guide maps intent → skills. If the user only asked a narrow question, use the narrow skill instead of the whole pipeline.

> **If you reach this skill without having loaded yt-guide, stop and load it now.**

---

## Choose the audit mode FIRST

| Mode | Behavior | When to use |
|------|----------|-------------|
| **Strict** (default) | A FAILED required phase (1–6) **stops the audit**. Report `OVERALL: FAILED`, the phase that failed, and stop. Do not run later phases. | "Full audit", "diagnose my channel", user expects completeness |
| **Partial** (opt-in) | Independent phases continue after a failure. Final result is labeled **`OVERALL: PARTIAL`** with every failure listed. | User wants "as much as possible", time-boxed, or some phases genuinely cannot run (e.g. no CSV) |

- **Ask the user once** which mode they want if unclear. Default = **strict**.
- **Partial mode never silently degrades** — the final answer must begin with "PARTIAL AUDIT" and list what was not measured.
- Never call a partial audit "complete" or a strict audit that stopped "done".

---

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
python skills/youtube/scripts/ytdata.py latest "@handle" --limit 10 --with-duration
python skills/youtube/scripts/ytdata.py home "@handle"
python skills/youtube/scripts/ytdata.py profile "@handle"
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

**This phase means invoking the yt-script skill — load it and run its script:**

```bash
# Score hooks from transcripts:
python skills/yt-script/scripts/hookscore.py "<transcript_file.json>" --json
```

> Do **not** call `ytdata` here and claim "hooks analyzed" — hookscore is a different tool in a different skill.

### Phase 4: Title/Thumbnail Analysis (yt-package skill)

**Load the yt-package skill and run its script — do not approximate it with ytdata:**

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

> **Thumbnail honesty rule:** The `thumb` field is **user-supplied TEXT**. This skill scores *text*, never images. You may NOT claim you "analyzed the thumbnail image", "checked contrast", "evaluated the face", "scored the actual thumbnail", or invented text that was not supplied. If no thumbnail text/image was provided, the thumbnail phase is **not evaluated** — say so (`thumbnail_evaluated: false`). If an actual thumbnail image was supplied, you must say it is image-derived.

> **Heuristic disclaimer:** title.py scores are **heuristic quality signals**, not predictions of CTR or ranking. Never present them as "this will get X% CTR" or "YouTube will rank this #N".

### Phase 5: SEO / Keywords (youtube data skill — NOT the yt-seo skill)

```bash
python skills/youtube/scripts/ytdata.py keywords "niche" --patterns --json
python skills/youtube/scripts/ytdata.py compete "keyword" --top 10 --json
python skills/youtube/scripts/ytdata.py scorecard "<video_id>" --keyword "target" --json
python skills/youtube/scripts/ytdata.py trends "seed idea" --days 30 --verbose --json
python skills/youtube/scripts/ytdata.py gap "your seed" --competitor @theirhandle --json
```

**Keyword opportunity vs competition — do not confuse them:**
- `keywords` outputs **opportunity_score** (higher = MORE opportunity — a seed worth targeting). It is labeled `opportunity_score` / `score_meaning: "opportunity"`.
- `compete` outputs **competition_score** (higher = HARDER to rank — a head-term to avoid). It is labeled `competition_score` / `score_meaning: "competition_difficulty"`.
- Never report a competition_score as "opportunity" or vice-versa. State which is which in the final report.

> **Do not claim the yt-seo skill ran here.** These are `ytdata` (youtube data skill) commands. The `yt-seo` creator skill (description/tags writer) is a *different* skill — invoke it only if the user asks to write/optimize descriptions & tags, and mark it as invoked then.

### Phase 6: Outlier / Competitor Analysis (youtube data skill — NOT the yt-viral skill)

```bash
python skills/youtube/scripts/ytdata.py outliers "@handle" --min-ratio 2.0 --tab all --json
```

> **Do not claim the yt-viral skill ran here.** `ytdata outliers` is the youtube data skill. The `yt-viral` creator skill (formula naming / swipe file) is a *different* skill — invoke it only if you actually open its SKILL.md and run its scripts.

### Phase 7: Retention Analysis (yt-retention skill) — OPTIONAL but HIGH-LEVERAGE

```bash
# If user provides CSV export:
python skills/yt-retention/scripts/retention.py retention.csv --json
```

**Agent behavior**: If no CSV provided, **ask the user to export it** — this phase is optional but high-leverage. Say: *"For retention analysis, I need the audience-retention CSV from YouTube Studio (Analytics → Engagement → Audience Retention → Download). Can you upload it? If not, I'll skip."*

---

## Execution manifest (required)

For every audit, produce a manifest — a machine-readable JSON record of each phase. Save it as `manifest.json` in your temp working dir and use it to write the final answer.

Example manifest:

```json
{
  "mode": "strict",
  "channel": "@Moments_Unscriptedorignal",
  "phases": {
    "phase1": {"skill": "youtube", "command": "ytdata sections ...", "exit_code": 0, "status": "success", "artifact": "sections.json"},
    "phase2": {"skill": "transcript", "command": "gettranscript.py 9NDb3RH9N7M --format json", "exit_code": 429, "status": "failed"}
  },
  "claims": [
    {"text": "131 subs, 18 uploads", "evidence": "MEASURED"}
  ]
}
```

Then (optionally but recommended) validate it:

```bash
python skills/yt-workflow/scripts/audit_manifest.py --manifest manifest.json --mode strict
```

**Manifest rules:**
- Record **every** phase you attempt, with the actual command, exit code, artifact path, and status: `success` | `failed` | `blocked` | `skipped` | `not_run`.
- A phase with non-zero exit code is **never** `success`.
- A phase you never ran is `not_run` — never mark it success.
- `thumbnail_evaluated: true` is allowed **only** with `thumbnail_basis: "image_artifact"`. Text alone can never justify it.
- Title/thumbnail/keyword scores carry a heuristic note — present them as heuristics, not predictions.

---

## Evidence & confidence (required in every final answer)

Every strategic claim must carry one of these labels:

| Label | Meaning | Example |
|-------|---------|---------|
| **MEASURED** | From tool output this session | "8,400 views, 64x subs (ytdata outliers)" |
| **INFERRED** | Logical from measured data, but not directly measured | "Topic demand is real (measured views); competition is too high (measured compete)" |
| **HYPOTHESIS** | Needs validation; don't act as fact | "A question-format title might lift CTR — untested for this channel" |

Never present a **HYPOTHESIS** as **MEASURED**. Never invent numbers, views, scores, or counts that weren't in the tool output. If 18 titles scored REWORK, say 18 REWORK — not "all" (two were REVISE in this channel's audit; count only what the tool actually returned).

---

## Pipeline Rules (Agent Must Follow)

1. **Phase 0 first** — consult yt-guide before selecting the chain.
2. **Ask for audit mode** if the user didn't specify: strict (default) or partial.
3. **Strict mode** — a FAILED required phase (1–6) stops the audit immediately. Report which phase failed and why. Do **not** continue to Phase N+1.
4. **Partial mode** — continue independent phases; every failure stays listed; final answer labeled `PARTIAL AUDIT`.
5. **Pass JSON between phases** — use `--json` flags, parse output.
6. **Invoke the actual skill** — run the skill's own scripts (hookscore for yt-script, title.py for yt-package). Using `ytdata` means the **youtube data skill** ran, nothing else.
7. **Record the manifest** — fill `manifest.json` as you go; report it at the end.
8. **Cache intermediates** — save JSON to temp files, pass paths forward.
9. **Handle missing data gracefully** — if optional phase data is missing (e.g., no retention CSV, no transcript for a video), note it in the output and continue. Don't halt the pipeline.
10. **Never fabricate** — no invented view counts, no invented thumbnail text, no "I saw the thumbnail" claims from text.
11. **Clean up downloaded artifacts** — yt-dlp may download thumbnail files (.webp, .jpg) and temp files. After each phase, delete any downloaded media files to avoid filling user disk space. Use `--no-thumbnails` flag when possible, or clean up `*.webp`, `*.jpg`, `*.mp4` files in the working directory after each command.

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
| **ytdata ≠ creator skills** | "Phase 3/4/5 done" because you ran ytdata commands | yt-script/yt-package/yt-seo/yt-viral only ran if you opened their SKILL.md and ran their scripts |
| **Thumbnail text = thumbnail image** | "I analyzed your thumbnail; contrast is weak" | Text-only scoring says nothing about the actual image. Mark `thumbnail_evaluated: false` |
| **Strict audit that "completed"** | Transcript failed (429) yet report says "full audit done" | Strict stops at the failure. Partial labels everything `PARTIAL AUDIT` |
| **Failure = success** | Non-zero exit code, phase marked "done" | Exit code governs status; a failed phase is never success |
| **Heuristic = prediction** | "This title will 3x your CTR" | Heuristic score is a signal, not a forecast. Say "heuristic score: 47/100" |
| **Invented counts** | "all 18 titles were REWORK" when the output had REVISE+REWORK | Quote the exact counts from tool output |
| **Opportunity vs competition confusion** | "space facts for kids, score 100 — great opportunity" | 100 = easy to get suggested, but competition is HARD (verified channels, 6.4M median) — opportunity ≠ competition |

---

## Required Inputs per Phase

| Phase | Skill | Input | Output |
|-------|-------|-------|--------|
| 1 | youtube | @handle | Channel data (sections, videos, home, profile) |
| 2 | transcript | Top 3 video IDs | Full transcripts (JSON + timestamps) |
| 3 | yt-script | Transcripts | Hook metrics (words/sec, questions, numbers, second-person, etc.) per video |
| 4 | yt-package | Titles + hook scores | Title/thumbnail scores + briefs |
| 5 | youtube (data) | Niche + target video | Keywords (opportunity), competition scores, scorecards |
| 6 | youtube (data) | Channel + niche | Outliers (views/subs ratio), competitor gaps |
| 7 | yt-retention | Studio CSV (optional) | Drop-off points, retention curves |

---

## Example Agent Prompt

```text
Run a full channel analysis on @Moments_Unscriptedorignal. Mode: strict.

Phase 0: load yt-guide, confirm the chain.
Phase 1: sections, channel, latest, home, profile (--json)
Phase 2: transcripts for top 3 videos (--format json --all-langs)
Phase 3: yt-script hookscore on each transcript
Phase 4: yt-package title scoring on last 10 titles
Phase 5: youtube keywords (opportunity) + compete (competition) + scorecard
Phase 6: youtube outliers
Phase 7 (optional): if user provides Studio CSV, run retention.py

Maintain manifest.json as you go. Label every claim MEASURED/INFERRED/HYPOTHESIS.
If any required phase fails: strict → stop and report FAILED at that phase.
If user asked for partial: continue, label final answer PARTIAL AUDIT.
Final answer = ONE biggest fix, 3 working things, what NOT to do.
```

---

## What Each Phase Produces

| Phase | Skill | Output |
|-------|-------|--------|
| 1 | youtube | Channel profile, videos list, sections, home tab data |
| 2 | transcript | Transcript JSON per video |
| 3 | yt-script | Hook metrics per video (raw stats, not a 0-100 score) |
| 4 | yt-package | Title/thumbnail scores (heuristic, not CTR predictions) |
| 5 | youtube (data) | Keywords (opportunity_score), competition (competition_score), scorecard |
| 6 | youtube (data) | Outlier videos (views/subs ratio), velocity |
| 7 | yt-retention | Retention curves, drop-off points (optional) |

The agent synthesizes all phases into: **one biggest fix + 3 things working + what NOT to do** — with every claim labeled MEASURED/INFERRED/HYPOTHESIS.
