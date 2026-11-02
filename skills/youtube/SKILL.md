---
name: youtube
description: "Use for YouTube research and data — free, no API key: searching videos/channels on a topic, browsing a channel's uploads, latest uploads, listing a playlist, counting a channel's sections (videos/shorts/shows/streams/playlists/community posts), reading community posts (paginated), scraping a channel's home page shelves / featured channels, listing Shows, or pulling a video's stats (views, likes, date, tags). Triggers on research tasks like 'what's working in X niche', 'find videos about Y', 'what has @creator posted', competitor analysis, trend spotting, community/post activity, channel network/featured channels, or when a user names a creator/topic and wants YouTube data. For the spoken text/transcript of a single video, use the `transcript` skill instead."
---

# YouTube Research

**Pipeline Position:** Phase 1 — Data Collection
**Outputs:** channel data (sections, videos, home, profile, latest) → feeds transcript, yt-seo, yt-viral, yt-audit
**Triggers:** "search X", "analyze @channel", "what's working in niche", "channel stats"

Search, browse, and analyze YouTube via local `yt-dlp` — **free, no API key, no credits, no rate limits for normal use.**

## Prerequisites

`yt-dlp` is installed on this machine. If missing: `python -m pip install --user -U yt-dlp`. Run as a module (`python -m yt_dlp`) — the exe may not be on PATH.

## How to use

Helper script at `scripts/ytdata.py` (relative to this SKILL.md). Subcommands:

```bash
python scripts/ytdata.py search "query" --limit 10          # find videos on a topic
python scripts/ytdata.py profile "@handle"                  # channel About/profile section
python scripts/ytdata.py sections "@handle"                 # count every tab: videos/shorts/shows/playlists/posts
python scripts/ytdata.py home "@handle"                     # Home tab shelves (featured video, Featured Channels)
python scripts/ytdata.py channel "@handle" --limit 15       # a channel's uploads
python scripts/ytdata.py channel "@handle" --tab shorts     # or: videos (default) | shorts | streams
python scripts/ytdata.py latest "@handle" --limit 10        # most recent uploads
python scripts/ytdata.py posts "@handle" --limit 30         # community posts — paginates past page 1
python scripts/ytdata.py shows "@handle"                    # Shows tab (episode collections, like playlists)
python scripts/ytdata.py playlist "<playlist-url>" --limit 20
python scripts/ytdata.py info "<video-url-or-id>"           # full stats for one video
```

Add `--json` to any command for structured output (use when you need to post-process). Default is readable text. `home --verbose` also lists each shelf's individual videos/channels.

Accepts `@handles`, full channel/playlist URLs, or bare video IDs.

## What each returns

| Command | Data |
| ------- | ---- |
| `search` | Videos matching a query — title, duration, views, channel, URL |
| `profile` | A channel's About section — name, handle, subscriber count, description, tags (= ALL channel keywords), video count |
| `sections` | Counts for every tab at once — videos, shorts, streams, shows, playlists, community posts |
| `home` | Home-tab shelves — featured video, Shorts, playlists, posts, **Featured Channels** (names + URLs) |
| `channel` | A channel's uploads (optionally Shorts or live Streams tab) |
| `latest` | Most recent uploads, reverse-chronological |
| `posts` | Community posts — text, author, published time, like count, post URL. Paginated: `--limit 30` reaches ~3 pages back |
| `shows` | A channel's Shows — title, episode count, URL (only some channels have a Shows tab) |
| `playlist` | Every video in a playlist — title, duration, views |
| `info` | One video's full stats: views, likes, subscribers, upload date, duration, tags, categories, description |

> **How `posts` and `home` work:** yt-dlp can't read the community tab (returns 0 entries) or the Home tab ("no home tab"), so these bypass it with a raw scrape of YouTube's own `ytInitialData` page data. `posts` tries `/posts` first (works everywhere tested; `/community` sometimes says "isn't available"), then **paginates via Innertube continuation POSTs** — the same request the browser makes when you scroll the feed. `home` parses the Home tab's shelves directly. Pure `urllib`, no API key, no credits.

## Research workflows

- **"What's working in [niche]?"** → `search "<topic>" --limit 20` to see titles + view counts, then `info` the outliers to get exact numbers.
- **"Analyze a competitor"** → `sections "@handle"` first to size them up (videos/shorts/shows/playlists/posts), then `home "@handle"` to see how they feature their content, `channel "@handle" --limit 30` or `latest` for recent activity, then `info` their top videos.
- **"Find videos about X and summarize"** → `search` to pick videos, then hand the video IDs to the `transcript` skill for the spoken text.
- **"What has this creator posted lately?"** → `latest "@handle"` for videos, `posts "@handle" --limit 30` for community/text posts (goes back months, not just page 1).
- **"How active is this channel / what's their posting mix?"** → `sections "@handle"` gives every count in one call.
- **"What channels does this creator promote / who's in their network?"** → `home "@handle"` → the Featured Channels shelf lists them with URLs.

## Behavior & limits

- Uses flat-playlist extraction — fast, but view counts can occasionally be `?` (not exposed on that surface). Use `info` on a specific video for exact stats.
- `search` is video-focused. To find a *channel*, search its name then read the channel from results, or go straight to `channel "@handle"` if you know it.
- Playlist/channel listings paginate internally; `--limit` caps what's pulled.
- `posts` paginates via continuation tokens: roughly 10 posts per page, so `--limit 30` ≈ 3 pages / several months back. Each page is one HTTP POST — keep `--limit` sane (≤100) to avoid throttling.
- `sections` reads page 1 + one continuation probe, so community counts show `N+` when more pages exist (exact when it fits on one page).
- `shows` / `home` / `posts` work without yt-dlp (pure HTTP); everything else runs through it.
- YouTube may throttle (HTTP 429) if you hammer it — add a small delay between many calls.
- Fails clearly on private/age-restricted/nonexistent targets.

## Scope

This skill handles **search, channels, playlists, metadata, community posts (paginated), home sections, Shows, and tab counts**. It does **not** pull transcripts — for the spoken text of a video, use the `transcript` skill (also free, also yt-dlp).

Both former yt-dlp gaps are filled free: `posts` (community feed via raw scrape + Innertube continuation) and `home` (Home-tab shelves incl. Featured Channels) — plus `shows`, `sections`, and everything else via yt-dlp. No paid API involved anywhere.

## Tips

- Pair with `transcript`: research with this, then pull text with `transcript`.
- Prefer `info` when you need real numbers (views/likes) for a single video — `search`/`channel` counts are sometimes approximations.
- For a channel you already have the URL for, `channel` accepts it directly.
