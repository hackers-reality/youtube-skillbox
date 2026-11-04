# YouTube Skillbox

Free YouTube research toolkit — search, keywords, competition, rank tracking, SEO scorecard, outliers, content gap, trends. No user-supplied YouTube Data API key required.

## Quick Start

```bash
pip install youtube-skillbox
ytdata --help
```

## Commands

| Command | Description |
|---------|-------------|
| `search <query>` | Search YouTube videos (locale-pinned via `--gl`/`--hl`) |
| `channel <handle>` | List channel uploads / shorts / streams |
| `latest <handle>` | Most recent uploads |
| `info <url>` | Full metadata for one video (views, likes, tags, description) |
| `scorecard <url>` | SEO checklist for a video (title/desc/tags/keyword fit) |
| `outliers <handle>` | Videos overperforming their channel (views/subs ratio) |
| `keywords <seed>` | Keyword ideas + relative volume from YouTube suggest |
| `compete <query>` | Competition score (0–100) from live SERP |
| `trends <seed>` | Historical trend for a seed keyword |
| `track <query> --video <url>` | Rank tracking for a video |
| `gap <seed> --competitor <handle>` | Content gap analysis |
| `profile <handle>` | Channel About/profile section |
| `sections <handle>` | Count every tab/section of a channel |
| `posts <handle>` | Community posts (paginated) |
| `shows <handle>` | Channel Shows (episode collections) |
| `home <handle>` | Home tab shelves (featured video, sections, Featured Channels) |
| `playlist <url>` | List playlist videos |

## Common Flags

- `--json` — Emit structured JSON output
- `--limit N` — Max results (default 10)
- `--gl XX --hl YY` — Pin region + language (default US/en)
- `--full-meta` — Enrich results with full metadata (upload_date, live_status, tags, likes, subscribers, categories)

## Use Cases

- **Keyword research** — `ytdata keywords "youtube seo" --json`
- **Competition analysis** — `ytdata compete "MrBeast challenge" --json`
- **Video SEO audit** — `ytdata scorecard "https://youtu.be/..." --json`
- **Channel research** — `ytdata channel "@MrBeast" --limit 20 --full-meta --json`
- **Rank tracking** — `ytdata track "youtube seo" --video "https://youtu.be/..." --json`
- **Find outliers** — `ytdata outliers "@channel" --json`
- **Content gap** — `ytdata gap "my topic" --competitor "@competitor" --json`

## No API Key Required

All data via `yt-dlp` + custom YouTube scrapers. Zero credits, no expiry, $0 forever.

## License

MIT