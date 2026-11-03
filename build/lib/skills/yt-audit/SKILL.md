---
name: yt-audit
description: DEPRECATED — Use yt-workflow instead. This skill is retained for reference only.
---
# yt-audit (DEPRECATED)

**This skill is deprecated. Use `yt-workflow` instead.**

The `yt-audit` skill has been replaced by `yt-workflow`, which provides a more comprehensive 7-phase channel analysis pipeline.

## Migration

Replace any usage of `yt-audit` with `yt-workflow`:

```bash
# Old (deprecated)
# yt-audit would run a monolithic audit

# New (canonical) - 7-phase pipeline
# Phase 1: Data Collection
python skills/youtube/scripts/ytdata.py sections "@handle"
python skills/youtube/scripts/ytdata.py channel "@handle" --limit 20 --with-duration
python skills/youtube/scripts/ytdata.py latest "@handle" --limit 10 --with-duration
python skills/youtube/scripts/ytdata.py home "@handle"
python skills/youtube/scripts/ytdata.py profile "@handle"

# Phase 2: Content Extraction
python skills/transcript/scripts/gettranscript.py "<video_id>" --format json --all-langs

# Phase 3: Hook Analysis
python skills/yt-script/scripts/hookscore.py "<transcript_file.json>" --json

# Phase 4: Title/Thumbnail Analysis
python skills/yt-package/scripts/title.py --file titles.json --json

# Phase 5: SEO / Keywords
python skills/youtube/scripts/ytdata.py keywords "niche" --patterns --json
python skills/youtube/scripts/ytdata.py compete "keyword" --top 10 --json
python skills/youtube/scripts/ytdata.py scorecard "<video_id>" --keyword "target" --json

# Phase 6: Outlier / Competitor Analysis
python skills/youtube/scripts/ytdata.py outliers "@handle" --min-ratio 2.0 --tab all --json

# Phase 7: Retention Analysis (optional)
python skills/yt-retention/scripts/retention.py retention.csv --json
```

## Key Differences from yt-audit

| yt-audit (deprecated) | yt-workflow (canonical) |
|------------------------|--------------------------|
| Monolithic audit | 7-phase modular pipeline |
| No explicit transcript phase | Explicit transcript extraction phase |
| No hook scoring | Explicit hook scoring (yt-script) |
| No title/thumbnails scoring | Explicit title/thumbs scoring (yt-package) |
| No SEO/keyword phase | Explicit SEO/keywords phase |
| No outlier/competitor phase | Explicit outlier/competitor phase |
| Retention required | Retention optional (Phase 7) |
| Voice.md prerequisite | No voice.md required |

## References

- See `skills/yt-workflow/SKILL.md` for the complete pipeline documentation
- See `skills/youtube/scripts/ytdata.py` for the shared data module