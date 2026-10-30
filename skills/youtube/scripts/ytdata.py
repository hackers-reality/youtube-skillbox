#!/usr/bin/env python3
"""
YouTube research via yt-dlp + raw page scraping: search, channels, playlists,
metadata, community posts (paginated), home sections, shows. No API key, no credits.

Subcommands:
  search   <query>              Search YouTube videos.
  profile  <handle-or-url>      Channel About/profile section.
  sections <handle-or-url>      Count every tab (videos/shorts/shows/playlists/posts).
  channel  <handle-or-url>      List a channel's uploads.
  latest   <handle-or-url>      Most recent uploads (reverse-chronological).
  posts    <handle-or-url>      Community posts — paginates past the first page.
  home     <handle-or-url>      Home tab shelves (Featured Channels, sections).
  shows    <handle-or-url>      Channel Shows (episode collections).
  playlist <url-or-id>          List a playlist's videos.
  info     <url-or-id>          Full metadata for one video (views, likes, date, tags).

Common flags:
  --limit N        Max results (default 10; max ~50 per call for search).
  --json           Emit structured JSON instead of readable text.
  --tab            channel only: videos (default) | shorts | streams

Requires: pip install yt-dlp  (posts/home/shows use raw HTTP and work without it)
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_ytdlp(args):
    cmd = [sys.executable, "-m", "yt_dlp"] + args + ["--no-warnings"]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


# ---- Community posts via raw Innertube page scrape (no yt-dlp; it can't do this) ----

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
       "Accept-Language": "en-US,en;q=0.9"}


def _http_get(url):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _extract_ytInitialData(html):
    """Pull the ytInitialData blob. YouTube serves it as `var ytInitialData`,
    `window["ytInitialData"]`, etc. — try every known form."""
    for pat in (r"var ytInitialData\s*=\s*(\{.*?\});</script>",
                r"window\[.ytInitialData.\]\s*=\s*(\{.*?\});",
                r"ytInitialData\s*=\s*(\{.*?\});"):
        m = re.search(pat, html, re.S)
        if not m:
            continue
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
    return None


def _extract_ytcfg(html):
    """Pull INNERTUBE_API_KEY + INNERTUBE_CONTEXT from the page's ytcfg blob."""
    m = re.search(r"ytcfg\.set\((\{.*?\})\);", html, re.S)
    if not m:
        return None, None
    try:
        cfg = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None, None
    return cfg.get("INNERTUBE_API_KEY"), cfg.get("INNERTUBE_CONTEXT")


def _innertube_browse(token, api_key, context):
    """POST to the Innertube browse endpoint with a continuation token.

    This is exactly what the browser does when you scroll the community feed —
    the token IS the 'next page'.
    """
    payload = json.dumps({"context": context, "continuation": token}).encode("utf-8")
    url = f"https://www.youtube.com/youtubei/v1/browse?key={api_key}"
    headers = dict(_UA, **{"Content-Type": "application/json"})
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _first_continuation(obj, path=""):
    """Find the feed's continuation token, preferring it over chip-bar/filter tokens.

    The community page can carry several continuationCommand tokens (feed +
    filter-chip bar). The feed's is the one not under a 'chip' path.
    """
    def scan(o, p):
        """Returns (score, token) or None — score 1 = feed, 0 = chip bar."""
        best = None
        if isinstance(o, dict):
            cc = o.get("continuationCommand")
            if isinstance(cc, dict) and isinstance(cc.get("token"), str) and len(cc["token"]) >= 50:
                score = 0 if re.search(r"chip", p, re.I) else 1
                best = (score, cc["token"])
            for k, v in o.items():
                r = scan(v, f"{p}.{k}")
                if r and (best is None or r[0] > best[0]):
                    best = r
        elif isinstance(o, list):
            for i, v in enumerate(o):
                r = scan(v, f"{p}[{i}]")
                if r and (best is None or r[0] > best[0]):
                    best = r
        return best

    best = scan(obj, path)
    return best[1] if best else None


def _find_renderers(obj, key):
    """Yield every dict stored under the given renderer key."""
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], dict):
            yield obj[key]
        for v in obj.values():
            yield from _find_renderers(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from _find_renderers(v, key)


def _runs_text(node):
    """Flatten a YouTube runs node into a plain string."""
    if not isinstance(node, dict):
        return ""
    runs = node.get("runs") or []
    if runs:
        return "".join(r.get("text", "") for r in runs)
    return node.get("simpleText", "") or ""


def _find_post_renderers(obj):
    """Recursively yield every backstagePostRenderer dict."""
    if isinstance(obj, dict):
        if "backstagePostRenderer" in obj:
            yield obj["backstagePostRenderer"]
        for v in obj.values():
            yield from _find_post_renderers(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _find_post_renderers(v)


def _parse_post(p):
    likes = (p.get("voteCount") or {}).get("simpleText")
    img = None
    att = p.get("attachment") or {}
    if "playlistVideoListRenderer" in att:
        img = "(playlist attachment)"
    shared = (att.get("videoThumbnailRenderer") or {})
    if shared:
        thumbs = ((shared.get("thumbnail") or {}).get("thumbnails") or [])
        if thumbs:
            img = thumbs[-1].get("url")
    return {
        "post_id": p.get("postId"),
        "author": _runs_text(p.get("authorText")),
        "text": _runs_text(p.get("contentText")),
        "published": _runs_text(p.get("publishedTimeText")),
        "likes": likes,
        "image_or_attachment": img,
        "url": f"https://www.youtube.com/post/{p.get('postId')}" if p.get("postId") else None,
    }


def _count_community(base):
    """Return (count, has_more) for a channel's community posts.

    Reads page 1, then probes ONE continuation page so '+' only shows when more
    posts genuinely exist (a lone feed token doesn't prove it).
    """
    for suffix in ("/posts", "/community"):
        try:
            html = _http_get(base + suffix)
        except Exception:
            continue
        data = _extract_ytInitialData(html)
        if not data:
            continue
        posts = [_parse_post(p) for p in _find_post_renderers(data)]
        if not posts:
            if suffix == "/posts":
                continue  # try the /community fallback
            return 0, False
        seen = {p["post_id"] for p in posts}
        token = _first_continuation(data)
        if not token:
            return len(posts), False
        key, ctx = _extract_ytcfg(html)
        if not key or not ctx:
            return len(posts), True
        try:
            resp = _innertube_browse(token, key, ctx)
        except Exception:
            return len(posts), True
        new = [p for p in (_parse_post(x) for x in _find_post_renderers(resp))
               if p["post_id"] and p["post_id"] not in seen]
        if not new:
            return len(posts), False
        return len(posts) + len(new), bool(_first_continuation(resp))
    return 0, False


def _paginate_posts(url, limit, max_pages=20):
    """Fetch the first page of posts, then follow continuation tokens — this is
    exactly what infinite-scroll does in the browser: each token is one more batch."""
    try:
        html = _http_get(url)
    except Exception as e:
        return [], str(e)
    data = _extract_ytInitialData(html)
    if not data:
        return [], "no ytInitialData"

    posts = [_parse_post(p) for p in _find_post_renderers(data)]
    seen = {p["post_id"] for p in posts if p["post_id"]}

    if len(posts) < limit:
        api_key, ctx = _extract_ytcfg(html)
        token = _first_continuation(data)
        if api_key and ctx and token:
            for _ in range(max_pages):
                if len(posts) >= limit:
                    break
                try:
                    resp = _innertube_browse(token, api_key, ctx)
                except Exception:
                    break  # token rejected / endpoint changed — keep what we have
                added = 0
                for p in (_parse_post(x) for x in _find_post_renderers(resp)):
                    if p["post_id"] and p["post_id"] not in seen:
                        seen.add(p["post_id"])
                        posts.append(p)
                        added += 1
                token = _first_continuation(resp)
                if not token or added == 0:
                    break
    return posts, None


def cmd_posts(a):
    base = a.posts if a.posts.startswith("http") else f"https://www.youtube.com/{a.posts}"
    base = base.rstrip("/")
    # If the user passed an explicit tab, honour just that one.
    if base.endswith("/posts"):
        candidates = [base]
    elif base.endswith("/community"):
        candidates = [base]
    else:
        # /posts works on every channel tested; /community sometimes shows
        # "This Community isn't available". Try both and merge.
        candidates = [base + "/posts", base + "/community"]

    all_posts, errs = [], []
    for url in candidates:
        # Roughly 10 posts/page, so pages ~= limit/10 (+1 for the first page).
        max_pages = max(1, min(20, a.limit // 10 + 2))
        posts, err = _paginate_posts(url, a.limit, max_pages)
        if err:
            errs.append(f"{url}: {err}")
        if posts:
            all_posts = posts
            break  # first source that yields posts wins (they're the same feed)

    # De-dupe by post_id, preserve order
    seen, uniq = set(), []
    for p in all_posts:
        if p["post_id"] and p["post_id"] not in seen:
            seen.add(p["post_id"])
            uniq.append(p)
    uniq = uniq[: a.limit]

    if a.json:
        print(json.dumps(uniq, ensure_ascii=False, indent=2))
        return
    if not uniq:
        print("No community posts found (channel may have none, or the tab layout changed).")
        for e in errs:
            print(f"  note: {e}", file=sys.stderr)
        return
    for i, p in enumerate(uniq, 1):
        print(f"{i}. [{p['published']}] ({p['likes']} likes) via {p['author']}")
        print(f"   {p['text']}")
        if p["image_or_attachment"]:
            print(f"   attachment: {p['image_or_attachment']}")
        if p["url"]:
            print(f"   {p['url']}")


def dump_entries(args):
    """Run yt-dlp in flat-playlist JSON mode and return a list of entry dicts."""
    proc = run_ytdlp(args + ["--flat-playlist", "--dump-json"])
    entries = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not entries:
        err = (proc.stderr or "").strip().splitlines()
        hint = err[-1] if err else "no results"
        print(f"ERROR: {hint}", file=sys.stderr)
        sys.exit(1)
    return entries


def fmt_views(n):
    if n is None:
        return "?"
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div:
            return f"{n/div:.1f}{unit}"
    return str(n)


def fmt_duration(s):
    if s is None:
        return "?"
    s = int(s)
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def slim(e):
    """Normalize an entry dict across search/channel/playlist (flat) shapes."""
    vid = e.get("id")
    url = e.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else None)
    channel = e.get("channel") or e.get("uploader") or e.get("playlist_channel") or e.get("channel_title")
    return {
        "id": vid,
        "title": e.get("title"),
        "url": url,
        "duration": e.get("duration"),
        "duration_string": e.get("duration_string") or fmt_duration(e.get("duration")),
        "views": e.get("view_count"),
        "channel": channel,
        "channel_url": e.get("channel_url") or e.get("uploader_url"),
        "verified": e.get("channel_is_verified"),
        "upload_date": e.get("upload_date") or e.get("timestamp"),
        "live_status": e.get("live_status"),
    }


def print_list(items, as_json):
    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    for i, it in enumerate(items, 1):
        dur = it.get("duration_string", "?")
        views = fmt_views(it.get("views"))
        ch = it.get("channel") or "?"
        verify = " ✓" if it.get("verified") else ""
        print(f"{i:>3}. {it.get('title')}")
        print(f"     {dur} | {views} views | {ch}{verify}")
        if it.get("url"):
            print(f"     {it['url']}")


def cmd_search(a):
    q = a.query.replace(":", " ").strip()
    args = [f"ytsearch{a.limit}:{q}"]
    entries = dump_entries(args)
    print_list([slim(e) for e in entries[: a.limit]], a.json)


def cmd_channel(a):
    base = a.handle if a.handle.startswith("http") else f"https://www.youtube.com/{a.handle}"
    if "/@" not in base and not base.rstrip("/").endswith(("/videos", "/shorts", "/streams")):
        base = base.rstrip("/") + "/videos"
    if a.tab in ("shorts", "streams") and not base.rstrip("/").endswith("/" + a.tab):
        base = base.rstrip("/").split("/videos")[0] + f"/{a.tab}"
    args = [base, "--playlist-items", f"1-{a.limit}"]
    entries = dump_entries(args)
    print_list([slim(e) for e in entries[: a.limit]], a.json)


def cmd_latest(a):
    # /videos tab is reverse-chronological by default, so the head is "latest".
    base = a.handle if a.handle.startswith("http") else f"https://www.youtube.com/{a.handle}"
    if not base.rstrip("/").endswith(("/videos", "/shorts")):
        base = base.rstrip("/") + "/videos"
    args = [base, "--playlist-items", f"1-{a.limit}"]
    entries = dump_entries(args)
    print_list([slim(e) for e in entries[: a.limit]], a.json)


def cmd_playlist(a):
    url = a.playlist if a.playlist.startswith("http") else a.playlist
    args = [url, "--playlist-items", f"1-{a.limit}"]
    entries = dump_entries(args)
    print_list([slim(e) for e in entries[: a.limit]], a.json)


def cmd_sections(a):
    base = a.sections if a.sections.startswith("http") else f"https://www.youtube.com/{a.sections}"
    base = base.rstrip("/")
    # Strip any existing tab suffix so we probe each tab from a clean base.
    for suf in ("/videos", "/shorts", "/streams", "/playlists", "/community"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    tabs = ["videos", "shorts", "streams", "playlists"]
    result = {"channel": base}
    for tab in tabs:
        proc = run_ytdlp(["--flat-playlist", "--dump-json", f"{base}/{tab}"])
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
        count = len(lines)
        # yt-dlp errors when a tab doesn't exist (e.g. no streams tab).
        if count == 0 and ("does not have" in (proc.stderr or "") or proc.returncode != 0):
            result[tab] = None  # tab doesn't exist
        else:
            result[tab] = count

    # Shows tab: yt-dlp can't parse gridShowRenderer, so count via raw scrape.
    try:
        shows_html = _http_get(base + "/shows")
        shows_data = _extract_ytInitialData(shows_html)
        n_shows = sum(1 for _ in _find_renderers(shows_data or {}, "gridShowRenderer"))
        # A channel without a Shows tab gets redirected to a page with no shows.
        result["shows"] = n_shows if n_shows else None
    except Exception:
        result["shows"] = None

    # Community posts: page 1 + one continuation probe for an honest count.
    n_posts, has_more = _count_community(base)
    result["community_posts"] = n_posts
    result["community_posts_more"] = has_more

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    def fmt(v, none="no tab"):
        return none if v is None else v

    print(f"Channel: {base}")
    print(f"  videos   : {fmt(result['videos'])}")
    print(f"  shorts   : {fmt(result['shorts'])}")
    print(f"  streams  : {fmt(result['streams'])}")
    print(f"  shows    : {fmt(result['shows'])}")
    print(f"  playlists: {fmt(result['playlists'])}")
    more = "+" if result["community_posts_more"] else ""
    print(f"  community: {result['community_posts']}{more} posts (use `posts` to read them)")


def cmd_shows(a):
    """List a channel's Shows — episode collections (YouTube treats them as playlists)."""
    base = a.shows if a.shows.startswith("http") else f"https://www.youtube.com/{a.shows}"
    base = base.rstrip("/")
    for suf in ("/videos", "/shorts", "/streams", "/playlists", "/community", "/posts", "/shows"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    try:
        html = _http_get(base + "/shows")
    except Exception as e:
        print(f"ERROR: could not fetch shows tab: {e}", file=sys.stderr)
        sys.exit(1)
    data = _extract_ytInitialData(html)
    if not data:
        print("ERROR: could not parse the shows tab.", file=sys.stderr)
        sys.exit(1)

    items = []
    for s in _find_renderers(data, "gridShowRenderer"):
        ep = (s.get("navigationEndpoint") or {}).get("browseEndpoint", {})
        show_url = None
        wm = (s.get("navigationEndpoint") or {}).get("commandMetadata", {}).get("webCommandMetadata", {})
        if wm.get("url"):
            show_url = "https://www.youtube.com" + wm["url"].split("?")[0]
        playlist_id = ep.get("browseId")
        if playlist_id and playlist_id.startswith("VL"):
            playlist_id = playlist_id[2:]  # VLPLxyz -> PLxyz
        count = None
        for ov in s.get("thumbnailOverlays") or []:
            t = (ov.get("thumbnailOverlayBottomPanelRenderer") or {}).get("text")
            if t:
                count = _runs_text(t)
        items.append({
            "title": (s.get("title") or {}).get("simpleText") or _runs_text(s.get("title")),
            "videos": count,
            "byline": _runs_text(s.get("shortBylineText")),
            "playlist_id": playlist_id,
            "url": show_url or (f"https://www.youtube.com/playlist?list={playlist_id}" if playlist_id else None),
        })
    items = items[: a.limit]
    if a.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    if not items:
        print("No Shows tab on this channel (only some channels have one).")
        return
    for i, it in enumerate(items, 1):
        print(f"{i:>3}. {it['title']}")
        if it["videos"]:
            print(f"     {it['videos']}")
        if it["url"]:
            print(f"     {it['url']}")


# renderers that represent a single home-shelf item, mapped to their kind.
# (richItemRenderer deliberately excluded: it WRAPS other renderers, which the
# walk finds on their own — counting it too would double-count items.)
_HOME_ITEM_KINDS = {
    "gridVideoRenderer": "video", "videoRenderer": "video", "lockupViewModel": "lockup",
    "gridPlaylistRenderer": "playlist", "playlistRenderer": "playlist",
    "gridChannelRenderer": "channel", "channelRenderer": "channel",
    "reelItemRenderer": "short", "shortsLockupViewModel": "short",
    "backstagePostRenderer": "post", "postRenderer": "post",
}


def _home_item(kind_node):
    """Extract (kind, id, title, url) from a single home-shelf item node."""
    (key, node), = kind_node.items()
    if key == "lockupViewModel":
        cid = node.get("contentId") or ""
        if cid.startswith("UC") and len(cid) == 24:
            kind = "channel"
        elif cid[:2] in ("PL", "UU", "OL", "RD", "FL", "MN", "TL", "PU", "LM") or cid.startswith("OLAK5uy"):
            kind = "playlist"
        else:
            kind = "video"
        title = None
        md = ((node.get("metadata") or {}).get("lockupMetadataViewModel") or {})
        title = md.get("title", {}).get("content") if isinstance(md.get("title"), dict) else None
        title = title or _runs_text(node.get("title"))
        url = {"video": f"https://www.youtube.com/watch?v={cid}",
               "playlist": f"https://www.youtube.com/playlist?list={cid}",
               "channel": f"https://www.youtube.com/channel/{cid}"}[kind]
        return kind, cid, title, url
    if key in ("gridVideoRenderer", "videoRenderer", "reelItemRenderer"):
        vid = node.get("videoId")
        return "video" if key != "reelItemRenderer" else "short", vid, _runs_text(node.get("title")) or _runs_text(node.get("headline")), (f"https://www.youtube.com/watch?v={vid}" if vid else None)
    if key in ("gridPlaylistRenderer", "playlistRenderer"):
        pid = node.get("playlistId")
        return "playlist", pid, _runs_text(node.get("title")), (f"https://www.youtube.com/playlist?list={pid}" if pid else None)
    if key in ("gridChannelRenderer", "channelRenderer"):
        cid = node.get("channelId") or (node.get("navigationEndpoint") or {}).get("browseEndpoint", {}).get("browseId")
        return "channel", cid, _runs_text(node.get("title")), (f"https://www.youtube.com/channel/{cid}" if cid else None)
    if key == "shortsLockupViewModel":
        vid = (((node.get("onTap") or {}).get("innertubeCommand") or {})
               .get("reelWatchEndpoint", {}).get("videoId"))
        if not vid:
            eid = node.get("entityId") or ""
            vid = eid.rsplit("-", 1)[-1] if "-" in eid else None
        return "short", vid, node.get("accessibilityText"), (f"https://www.youtube.com/shorts/{vid}" if vid else None)
    if key in ("backstagePostRenderer", "postRenderer"):
        return "post", node.get("postId"), _runs_text(node.get("contentText")), (f"https://www.youtube.com/post/{node.get('postId')}" if node.get("postId") else None)
    return key.replace("Renderer", "").replace("ViewModel", "").lower(), None, None, None


def cmd_home(a):
    """Parse the channel's Home tab shelves — featured video, shorts, playlists,
    Featured Channels, and any custom sections (what the paid API's 'sections' did)."""
    base = a.home if a.home.startswith("http") else f"https://www.youtube.com/{a.home}"
    base = base.rstrip("/")
    for suf in ("/videos", "/shorts", "/streams", "/playlists", "/community", "/posts", "/shows", "/home"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    try:
        html = _http_get(base)
    except Exception as e:
        print(f"ERROR: could not fetch channel home: {e}", file=sys.stderr)
        sys.exit(1)
    data = _extract_ytInitialData(html)
    if not data:
        print("ERROR: could not parse the home tab.", file=sys.stderr)
        sys.exit(1)

    try:
        tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
        content = tabs[0].get("tabRenderer", {}).get("content", {})
        sections = content.get("sectionListRenderer", {}).get("contents", [])
    except (KeyError, AttributeError):
        sections = []

    out = []
    for sec in sections:
        inner_list = (sec.get("itemSectionRenderer") or {}).get("contents") or []
        for inner in inner_list:
            top_key = next(iter(inner), None)
            node = inner.get(top_key, inner)
            # section title
            title = None
            for cand in (node.get("title") if isinstance(node, dict) else None,):
                if isinstance(cand, dict):
                    title = _runs_text(cand) or None
                elif isinstance(cand, str):
                    title = cand
            if title is None:
                # view-model style titles
                for p, k, v in _walk_pairs(node):
                    if k in ("title", "content") and isinstance(v, str) and 0 < len(v) < 90:
                        title = v
                        break
                    if k == "title" and isinstance(v, dict):
                        t = _runs_text(v)
                        if t:
                            title = t
                            break
            # classify section type + collect items
            if top_key == "channelVideoPlayerRenderer":
                stype = "featured video"
                vid = node.get("videoId")
                vt = node.get("title")
                if isinstance(vt, dict):
                    vt = _runs_text(vt)
                elif not isinstance(vt, str):
                    vt = None
                items = [("video", vid, vt, f"https://www.youtube.com/watch?v={vid}" if vid else None)]
            else:
                # Generic: walk whatever renderers this section holds, so ANY
                # section type (known or future) still yields its items.
                items = [_home_item({k: v}) for k, v in _pairs_of_kind(node)]
                counts = {}
                for it in items:
                    counts[it[0]] = counts.get(it[0], 0) + 1
                dom = max(counts, key=counts.get) if counts else None
                stype = {"video": "videos", "short": "shorts", "playlist": "playlists",
                         "channel": "featured channels", "post": "posts"}.get(dom)
                if stype is None:
                    # no items: fall back to the renderer name (keeps the section visible)
                    stype = {"shelfRenderer": "shelf", "reelShelfRenderer": "shorts"}.get(
                        top_key,
                        (top_key or "section").replace("Renderer", "").replace("ViewModel", "").lower())
            out.append({"type": stype, "title": title, "count": len(items),
                        "items": [{"kind": k, "id": i, "title": t, "url": u}
                                  for k, i, t, u in items]})

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    if not out:
        print("No home sections found (tab layout may have changed).")
        return
    print(f"Home — {base}")
    for i, s in enumerate(out, 1):
        label = s["title"] or s["type"]
        print(f"{i:>3}. [{s['type']}] {label}  ({s['count']} item{'s' if s['count'] != 1 else ''})")
        for it in s["items"][: a.limit]:
            if it["kind"] == "channel":
                print(f"       - {it['title']}  {it['url']}")
            elif a.verbose and it["title"]:
                print(f"       - [{it['kind']}] {it['title']}")


def _walk_pairs(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path + "." + k, k, v
            yield from _walk_pairs(v, path + "." + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_pairs(v, path + f"[{i}]")


def _pairs_of_kind(node):
    """Yield (renderer_key, renderer_node) for every shelf item inside a node."""
    for p, k, v in _walk_pairs(node):
        if k in _HOME_ITEM_KINDS and isinstance(v, dict):
            yield k, v


def cmd_profile(a):
    base = a.profile if a.profile.startswith("http") else f"https://www.youtube.com/{a.profile}"
    proc = run_ytdlp(["--skip-download", "--dump-single-json", base])
    if proc.returncode != 0 or not proc.stdout.strip():
        err = (proc.stderr or "").strip().splitlines()
        print(f"ERROR: {err[-1] if err else 'could not fetch channel profile'}", file=sys.stderr)
        sys.exit(1)
    d = json.loads(proc.stdout)
    payload = {
        "name": d.get("channel") or d.get("uploader"),
        "handle": d.get("id"),
        "channel_url": d.get("webpage_url") or d.get("channel_url"),
        "subscribers": d.get("channel_follower_count"),
        "video_count": d.get("playlist_count") or d.get("upload_count"),
        "total_views": d.get("view_count"),
        "description": d.get("channel_description") or d.get("description"),
        "tags": d.get("tags"),
        "country": d.get("channel_country") or d.get("country"),
    }
    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for k, v in payload.items():
        if v is not None and v != []:
            if isinstance(v, str) and len(v) > 600:
                v = v[:600] + "..."
            print(f"{k:>13}: {v}")


def cmd_info(a):
    url = a.info if a.info.startswith("http") else f"https://www.youtube.com/watch?v={a.info}"
    proc = run_ytdlp(["--skip-download", "--dump-single-json", url])
    if proc.returncode != 0 or not proc.stdout.strip():
        err = (proc.stderr or "").strip().splitlines()
        print(f"ERROR: {err[-1] if err else 'could not fetch info'}", file=sys.stderr)
        sys.exit(1)
    d = json.loads(proc.stdout)
    payload = {
        "id": d.get("id"),
        "title": d.get("title"),
        "channel": d.get("channel") or d.get("uploader"),
        "channel_url": d.get("channel_url") or d.get("uploader_url"),
        "subscribers": d.get("channel_follower_count"),
        "views": d.get("view_count"),
        "likes": d.get("like_count"),
        "upload_date": d.get("upload_date"),
        "duration_seconds": d.get("duration"),
        "duration_string": d.get("duration_string"),
        "live_status": d.get("live_status"),
        "categories": d.get("categories"),
        "tags": d.get("tags"),
        "description": (d.get("description") or "")[:800] or None,
    }
    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for k, v in payload.items():
        if v is not None:
            print(f"{k:>18}: {v}")


def main():
    ap = argparse.ArgumentParser(description="YouTube research via yt-dlp (no API key).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="Search videos")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("channel", help="List channel uploads")
    p.add_argument("handle", help="@handle, channel URL, or UC... ID")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--tab", choices=["videos", "shorts", "streams"], default="videos")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_channel)

    p = sub.add_parser("latest", help="Most recent uploads")
    p.add_argument("handle", help="@handle or channel URL")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_latest)

    p = sub.add_parser("playlist", help="List playlist videos")
    p.add_argument("playlist", help="Playlist URL or ID")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_playlist)

    p = sub.add_parser("profile", help="Channel profile / About section")
    p.add_argument("profile", help="@handle or channel URL")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("posts", help="Community posts (raw scrape; yt-dlp can't do this)")
    p.add_argument("posts", help="@handle or channel URL")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_posts)

    p = sub.add_parser("sections", help="Count every tab/section of a channel")
    p.add_argument("sections", help="@handle or channel URL")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_sections)

    p = sub.add_parser("shows", help="List a channel's Shows (episode collections)")
    p.add_argument("shows", help="@handle or channel URL")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_shows)

    p = sub.add_parser("home", help="Home tab shelves (featured video, sections, Featured Channels)")
    p.add_argument("home", help="@handle or channel URL")
    p.add_argument("--limit", type=int, default=10, help="max items listed per shelf")
    p.add_argument("--verbose", action="store_true", help="also list each shelf's video/playlist items")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_home)

    p = sub.add_parser("info", help="Full metadata for one video")
    p.add_argument("info", help="Video URL or ID")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_info)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
