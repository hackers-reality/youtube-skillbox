---
name: yt-audit
description: DEPRECATED — This subcommand has been removed. Use yt-workflow instead.
---

# yt-audit (DEPRECATED)

This subcommand has been removed. Use the yt-workflow pipeline instead:

```bash
# Run the full pipeline manually:
python scripts/ytdata.py sections "@handle"
python scripts/ytdata.py channel "@handle" --limit 20 --with-duration
python scripts/ytdata.py latest "@handle" --limit 10 --with-duration
python scripts/ytdata.py home "@handle"
python scripts/ytdata.py profile "@handle"
python scripts/transcript/scripts/gettranscript.py "<video_id>" --format json --all-langs
python scripts/yt-script/scripts/hookscore.py "<transcript.json>" --json
python scripts/yt-package/scripts/title.py --titles titles.txt --keyword "keyword"
python scripts/yt-seo/scripts/ytdata.py keywords "niche" --patterns --json
python scripts/yt-seo/scripts/ytdata.py compete "keyword" --top 10 --json
python scripts/yt-viral/scripts/viral.py "@handle" --json
```

See `skills/yt-workflow/SKILL.md` for the complete pipeline documentation.