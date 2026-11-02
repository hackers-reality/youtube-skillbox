---
name: yt-workflow
description: Orchestrate multi-skill YouTube audits — chains youtube → transcript → yt-script → yt-package → yt-seo → yt-viral → yt-retention → yt-audit. Use for "audit my channel", "why isn't this growing", "full channel review", "analyze competitor".
---

# yt-workflow: The Orchestration Layer

## When to use
Any "audit my channel" / "why isn't this growing" / "full channel review" / "analyze competitor" request.

## The Pipeline (run in order, each feeds the next)

### Phase 1: Data Collection (youtube skill)
```bash
python ../youtube/scripts/ytdata.py sections "@handle"
python ../youtube/scripts/ytdata.py channel "@handle" --limit 20 --with-duration
python ../youtube/scripts/ytdata.py latest "@handle" --limit 10 --with-duration
python ../youtube/scripts/ytdata.py home "@handle"
python ../youtube/scripts/ytdata.py profile "@handle"
```

### Phase 2: Content Extraction (transcript skill)
```bash
# For each of the 3 most recent videos:
python ../transcript/scripts/gettranscript.py "<video_id>" --format json
```

### Phase 3: Hook Analysis (yt-script skill)
```bash
# Score hooks from transcripts:
python ../yt-script/scripts/hookscore.py <transcript.json>
```

### Phase 4: Title/Thumbnail Audit (yt-package skill)
```bash
# Score titles from channel data:
python ../yt-package/scripts/title.py --titles titles.txt
```

### Phase 5: SEO/Keyword Audit (yt-seo skill)
```bash
python ../yt-seo/scripts/ytdata.py keywords "niche" --patterns
python ../yt-seo/scripts/ytdata.py compete "keyword" --top 10
python ../yt-seo/scripts/ytdata.py scorecard "<video_id>" --keyword "target"
```

### Phase 6: Outlier/Competitor Analysis (yt-viral skill)
```bash
python ../yt-viral/scripts/viral.py "@handle"
```

### Phase 7: Retention Analysis (yt-retention skill)
```bash
# If user provides CSV export:
python ../yt-retention/scripts/retention.py retention.csv
```

### Phase 8: Final Audit (yt-audit skill)
```bash
# Synthesize all above into the ONE fix
```

---

## Pipeline Rules (Agent Must Follow)

1. **Never skip phases** — each phase produces required input for the next
2. **Pass JSON between phases** — use `--json` flags, parse output
3. **Fail fast** — if a phase fails, report what's missing and stop
4. **Cache intermediates** — save JSON to temp files, pass paths forward

---

## Required Inputs for yt-audit (Final Phase)

The audit skill requires these from previous phases:

| Input | Source Skill | Format |
|-------|--------------|--------|
| Channel data (sections, videos, home, profile) | youtube | JSON |
| Transcripts (3 most recent videos) | transcript | JSON |
| Hook scores (3 videos) | yt-script | JSON |
| Title scores (last 10 videos) | yt-package | JSON |
| Keywords + competition | yt-seo | JSON |
| Outliers (views/subs ratio) | yt-viral | JSON |
| Retention curves (if CSV provided) | yt-retention | JSON |

---

## Example Agent Prompt

```text
Run a full audit on @Moments_Unscriptedorignal:

1. Run youtube skill: sections, channel, latest, home, profile
2. Get transcripts for top 3 videos by views
3. Run yt-script hookscore on each transcript
4. Run yt-package title scoring on last 10 titles
5. Run yt-seo keywords for "space facts" niche
6. Run yt-viral outliers on channel
7. Synthesize with yt-audit

Output: single biggest fix, 3 working things, what NOT to do.
```