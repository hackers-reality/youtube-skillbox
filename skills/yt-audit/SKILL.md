---
name: yt-audit
description: DEPRECATED — This subcommand has been removed. Use yt-workflow instead.
---

# yt-audit (DEPRECATED)

This subcommand has been removed. Use the yt-workflow pipeline instead:

```bash
# Run the full pipeline manually:
python skills/youtube/scripts/ytdata.py sections "@handle"
python skills/youtube/scripts/ytdata.py channel "@handle" --limit 20 --with-duration
python skills/youtube/scripts/ytdata.py latest "@handle" --limit 10 --with-duration
python skills/youtube/scripts/ytdata.py home "@handle"
python skills/youtube/scripts/ytdata.py profile "@handle"
python skills/transcript/scripts/gettranscript.py "<video_id>" --format json --all-langs
python skills/yt-script/scripts/hookscore.py "<transcript.json>" --json
python skills/yt-package/scripts/title.py --file titles.json --json
python skills/youtube/scripts/ytdata.py keywords "niche" --patterns --json
python skills/youtube/scripts/ytdata.py compete "keyword" --top 10 --json
python skills/youtube/scripts/ytdata.py outliers "@handle" --min-ratio 2.0 --tab all --json
```

See `skills/yt-workflow/SKILL.md` for the complete pipeline documentation.