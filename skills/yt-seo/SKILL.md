---
name: yt-seo
description: >-
  Write the description, tags and search-facing text for a YouTube video,
  aimed at the query a real person types. Use for "write my description",
  "tags", "SEO", "help this video get found", "nobody is finding this".
---

# yt-seo

Search is a smaller lever than packaging and a bigger one than people think for evergreen videos.
For a video aimed at the subscriber feed, say so and spend the effort on `/yt-package` instead.

## Before you write

1. Read `~/.claude/youtube/voice.md` if it exists. That is the user's voice profile: how they talk
   on camera, the words they never use, who they are talking to, what they will not claim. If it
   does not exist, ask for **three of their own videos**, read or transcribe them, infer the voice,
   and write the file. A script in the wrong voice is worse than no script, because they have to
   read it out loud.
2. Never invent a number, a result or a source. If a figure would strengthen it and you do not have
   one, ask for it or write the line without it.

## Pick the query first

Research the keyword before writing a word of the copy — not after.

```bash
python skills/youtube/scripts/ytdata.py keywords "seed idea" --patterns
```

That expands the seed through **two** suggest engines — YouTube's own (what people type *on*
YouTube) and DuckDuckGo's (what the wider web asks) — across a–z plus `how` / `why` / `best` /
`for beginners` / `vs` / year patterns, then scores every idea by how often and how high it comes
back. Both are free, no API key; `--sources yt` restricts to YouTube alone. `Y` = it mentions the
current year (trending), `Q` = it is a question. Use `--gl` / `--hl` when the video targets a
specific market.

Take the top two or three the video can honestly deliver. The highest-scoring keyword you cannot
answer is a bounce, not traffic. Then check the competition — this tells you if the SERP is
penetrable or a wall:

```bash
python skills/youtube/scripts/ytdata.py compete "the keyword" --top 10
```

The score is 0–100 with a band (EASY / MEDIUM / HARD / SATURATED) and actionable advice.
A high score means the incumbents are big, old, verified and title-dense — you need a clearly
better video, not just a better title. Then check where you already stand:

```bash
python skills/youtube/scripts/ytdata.py track "the keyword" --video <your video url>
```

The score is 0–100 with a band (EASY / MEDIUM / HARD / SATURATED) and actionable advice.
A high score means the incumbents are big, old, verified and title-dense — you need a clearly
better video, not just a better title. Then check where you already stand:

```bash
python skills/youtube/scripts/ytdata.py track "the keyword" --video <your video url>
```

The position is logged with its history (`~/.ytdata-ranklog.json`), so a later run shows movement
instead of a one-off guess. Re-check after publishing, then again a week later.

## Historical trend (new)

Once you've run `keywords` a few times over days/weeks, see the trend:

```bash
python skills/youtube/scripts/ytdata.py trends "seed idea" --days 30 --verbose
```

Shows score trajectory (sparklines), velocity (↑/↓/→), and which keywords are gaining or losing demand.

## Content gap & outliers (new)

See what competitors target that you don't:

```bash
python skills/youtube/scripts/ytdata.py gap "your seed" --competitor @theirhandle
```

Find breakout videos in a niche (views/subs ratio):

```bash
python skills/youtube/scripts/ytdata.py outliers @handle --min-ratio 3
```

## SEO scorecard (new)

Before publishing, audit your metadata against the target keyword:

```bash
python skills/youtube/scripts/ytdata.py scorecard <video_url> --keyword "your keyword"
```

Returns 0–100 with weighted checks: title (keyword present, ≤60 chars), description (keyword in first 2 lines, ≥150 chars), tags (keyword present, 5–15 count), chapters (if >10 min), duration sanity, freshness (if keyword has year).

## The description

- **The first two lines are the only ones anyone reads.** They show above "...more" and they are
  the search snippet. Say what the video gives them, in the words they would have typed.
- Then the link or the resource, if there is one, so it is above the fold.
- Then chapters (`/yt-chapters` writes them).
- Then the long version: what is covered, who it is for, what it assumes.

## Tags, honestly

Tags are a weak signal and YouTube has said so. Use them for disambiguation - spellings, the tool
names, the abbreviations people actually type - and stop. Fifteen is plenty. A wall of tags is not
a strategy and stuffing unrelated ones is against the terms.

## The query test

Before handing anything over, write the three search queries this video should win — pull them from
`keywords`, not from your head — and check the title and first two description lines contain the
words in those queries. If they do not, the problem is the title, not the description.

## The gate

Nothing here publishes. This skill writes and you publish. Every output ends in a block the user
copies, and the last line of every run is the question: **ship it, or change it?**
