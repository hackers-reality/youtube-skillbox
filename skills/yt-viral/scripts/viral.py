#!/usr/bin/env python3
"""
Outlier Detection for YouTube Channels

Finds videos that overperform their channel average (views/subs ratio + velocity).
Identifies breakout content patterns.
"""
import json
import re
import sys
import argparse
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


def run_ytdlp(args: List[str]) -> subprocess.CompletedProcess:
    """Run yt-dlp as module."""
    cmd = [sys.executable, "-m", "yt_dlp"] + args
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def get_channel_stats(handle: str) -> Dict:
    """Get channel subscriber count and basic info."""
    base = handle if handle.startswith("http") else f"https://www.youtube.com/{handle}"
    proc = run_ytdlp(["--skip-download", "--dump-single-json", base])
    if proc.returncode != 0 or not proc.stdout.strip():
        return {}
    d = json.loads(proc.stdout)
    return {
        "channel": d.get("channel") or d.get("uploader"),
        "handle": d.get("id"),
        "channel_url": d.get("webpage_url") or d.get("channel_url"),
        "subscribers": d.get("channel_follower_count"),
        "total_views": d.get("view_count"),
        "video_count": d.get("playlist_count") or d.get("upload_count"),
    }


def get_videos(handle: str, limit: int = 50, tab: str = "videos") -> List[Dict]:
    """Fetch videos from channel with view counts."""
    base = handle if handle.startswith("http") else f"https://www.youtube.com/@{handle}"
    if not handle.startswith("http"):
        base = f"https://www.youtube.com/@{handle.lstrip('@')}"
    
    tab_suffix = f"/{tab}" if tab in ("videos", "shorts", "streams") else ""
    tab_url = base.rstrip("/") + tab_suffix
    
    proc = run_ytdlp([
        "--skip-download", "--flat-playlist", "--dump-json", tab_url,
        "--playlist-end", str(limit)
    ])
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    
    videos = []
    for line in proc.stdout.strip().splitlines():
        if line.strip().startswith("{"):
            try:
                d = json.loads(line)
                if d.get("id"):
                    videos.append(d)
            except json.JSONDecodeError:
                continue
    return videos


def get_video_details(vid: str) -> Optional[Dict]:
    """Get detailed stats for a single video."""
    proc = run_ytdlp(["--skip-download", "--dump-single-json", f"https://www.youtube.com/watch?v={vid}"])
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def parse_upload_date(date_str: str) -> Optional[datetime]:
    """Parse YYYYMMDD upload date."""
    if not date_str or len(date_str) != 8:
        return None
    try:
        return datetime(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    except ValueError:
        return None


def calculate_vph(view_count: int, upload_date: str) -> float:
    """Calculate views per hour since upload."""
    upload_dt = parse_upload_date(upload_date)
    if not upload_dt or view_count <= 0:
        return 0.0
    
    hours = (datetime.now() - upload_dt).total_seconds() / 3600
    if hours <= 0:
        return float(view_count)
    return view_count / hours


def analyze_outliers(channel_stats: Dict, videos: List[Dict], min_ratio: float = 2.0) -> List[Dict]:
    """Find videos that overperform channel average."""
    subs = channel_stats.get("subscribers", 0)
    if not subs:
        return []
    
    outliers = []
    for v in videos:
        vid = v.get("id")
        if not vid:
            continue
        
        # Get detailed stats
        detail = get_video_details(vid)
        if not detail:
            continue
        
        views = detail.get("view_count", 0) or v.get("view_count", 0)
        if not views:
            continue
        
        upload_date = detail.get("upload_date") or v.get("upload_date")
        vph = calculate_vph(views, upload_date) if upload_date else 0
        ratio = views / subs if subs > 0 else 0
        
        if ratio >= min_ratio:
            outliers.append({
                "video_id": vid,
                "title": detail.get("title", v.get("title")),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "views": views,
                "vph": round(vph, 1),
                "ratio": round(ratio, 2),
                "subscribers": subs,
                "upload_date": upload_date,
                "duration": detail.get("duration"),
                "tags": detail.get("tags"),
            })
    
    # Sort by ratio descending
    outliers.sort(key=lambda x: x["ratio"], reverse=True)
    return outliers


def analyze_velocity(videos: List[Dict], top_n: int = 10) -> List[Dict]:
    """Find fastest-growing videos (highest VPH)."""
    velocity = []
    for v in videos:
        vid = v.get("id")
        if not vid:
            continue
        detail = get_video_details(vid)
        if not detail:
            continue
        views = detail.get("view_count", 0) or v.get("view_count", 0)
        upload_date = detail.get("upload_date") or v.get("upload_date")
        if not views or not upload_date:
            continue
        vph = calculate_vph(views, upload_date)
        velocity.append({
            "video_id": vid,
            "title": detail.get("title", v.get("title")),
            "views": views,
            "vph": round(vph, 1),
            "upload_date": upload_date,
        })
    
    velocity.sort(key=lambda x: x["vph"], reverse=True)
    return velocity[:top_n]


def detect_content_gaps(channel_stats: Dict, competitor_handle: str, seed: str) -> Dict:
    """Find keyword gaps between your channel and competitor."""
    # Get your keywords
    # This would integrate with yt-seo/keywords
    pass


def main():
    parser = argparse.ArgumentParser(description="Find viral outliers and content gaps")
    parser.add_argument("handle", help="@handle, channel URL, or UC... ID")
    parser.add_argument("--min-ratio", type=float, default=2.0, help="Min views/subs ratio")
    parser.add_argument("--limit", type=int, default=50, help="Max videos to scan")
    parser.add_argument("--tab", choices=["videos", "shorts"], default="videos")
    parser.add_argument("--top-velocity", type=int, default=10, help="Top N by VPH")
    parser.add_argument("--competitor", help="Competitor handle for gap analysis")
    parser.add_argument("--seed", help="Seed keyword for gap analysis")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    # Resolve handle
    handle = args.handle.strip()
    if handle.startswith("http"):
        base = handle
    elif handle.startswith("@"):
        base = f"https://www.youtube.com/@{handle[1:]}"
    elif handle.startswith("UC") and len(handle) == 24:
        base = f"https://www.youtube.com/channel/{handle}"
    else:
        base = f"https://www.youtube.com/@{handle}"

    print(f"Analyzing {base}...", file=sys.stderr)

    # Get channel stats
    channel = get_channel_stats(base)
    if not channel:
        print("ERROR: Could not fetch channel", file=sys.stderr)
        sys.exit(1)
    
    print(f"Channel: {channel.get('channel')} ({channel.get('subscribers', 0):,} subs)", file=sys.stderr)

    # Get videos
    videos = get_videos(base, args.limit, args.tab)
    print(f"Scanning {len(videos)} videos...", file=sys.stderr)

    # Outliers
    outliers = analyze_outliers(channel, videos, args.min_ratio)
    
    # Velocity
    velocity = analyze_velocity(videos, args.top_velocity)

    # Output
    if args.json:
        print(json.dumps({
            "channel": channel,
            "outliers": outliers,
            "top_velocity": velocity,
            "scanned": len(videos),
            "min_ratio": args.min_ratio
        }, ensure_ascii=False, indent=2)
    else:
        print(f"\n=== OUTLIERS (ratio ≥ {args.min_ratio}x) ===")
        if outliers:
            for o in outliers:
                dur = ""
                if o.get("duration"):
                    h = o["duration"] // 3600
                    m = (o["duration"] % 3600) // 60
                    s = o["duration"] % 60
                    dur = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                print(f"  {o['ratio']:.1f}x  {o['vph']:>8,.0f} VPH  {str(o['views']):>10}  {dur:>8}  {o['title']}")
                print(f"       {o['url']}")
        else:
            print("  No outliers found at this threshold")

        print(f"\n=== TOP {args.top_velocity} BY VELOCITY (VPH) ===")
        for v in velocity:
            print(f"  {v['vph']:>8,.0f} VPH  {str(v['views']):>10}  {v['title']}")

if __name__ == "__main__":
    main()