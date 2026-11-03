#!/usr/bin/env python3
"""
YouTube Retention Analysis

Parses YouTube Studio audience-retention CSV export.
Identifies three leak types: HOOK LEAK, CLIFFS, SLIDE.
"""
import csv
import json
import sys
import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime


def parse_retention_csv(csv_path: str, video_duration_seconds: float = None) -> Dict:
    """Parse YouTube Studio audience retention CSV.
    
    Args:
        csv_path: Path to CSV file
        video_duration_seconds: If provided, converts percentage positions to seconds
    """
    rows = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize keys
            row = {k.strip().lower().replace(' ', '_').replace('%', 'pct').replace('(', '').replace(')', ''): v for k, v in row.items()}
            rows.append(row)
    
    if not rows:
        return {"error": "No data rows found"}
    
    # Find time and retention columns (multiple possible formats)
    time_col = None
    retention_col = None
    for col in rows[0].keys():
        col_lower = col.lower()
        # More specific matching to avoid picking wrong percentage columns
        if 'video_position' in col_lower:
            time_col = col
        elif 'elapsed' in col_lower and 'time' in col_lower:
            time_col = col
        elif 'time' in col_lower and 'position' in col_lower:
            time_col = col
        elif 'retention' in col_lower and 'audience' in col_lower:
            retention_col = col
        elif 'audience' in col_lower and 'retention' in col_lower:
            retention_col = col
    
    # Fallback: if no time column found, check for video position pct columns
    if not time_col:
        for col in rows[0].keys():
            col_lower = col.lower()
            if 'pct' in col_lower and 'video' in col_lower and 'position' in col_lower:
                time_col = col
                break
    
    # Fallback: if no retention column found
    if not retention_col:
        for col in rows[0].keys():
            col_lower = col.lower()
            if 'pct' in col_lower and 'audience' in col_lower and 'retention' in col_lower:
                retention_col = col
                break
    
    if not time_col or not retention_col:
        return {"error": f"Could not find time/retention columns. Columns: {list(rows[0].keys())}"}
    
    # Parse data points
    points = []
    time_is_pct = False
    for row in rows:
        try:
            time_val = row[time_col]
            # Check if time is in HH:MM:SS format or percentage
            if ':' in str(time_val):
                seconds = parse_time_to_seconds(time_val)
            else:
                # Percentage of video (0-100) - convert to seconds if duration known
                try:
                    pct = float(time_val)
                    time_is_pct = True
                    if video_duration_seconds:
                        seconds = (pct / 100.0) * video_duration_seconds
                    else:
                        seconds = pct  # Store as percentage for now
                except ValueError:
                    continue
            retention = float(row[retention_col].replace('%', '').replace(',', ''))
            points.append({"time_seconds": seconds, "retention_pct": retention, "time_is_pct": time_is_pct})
        except (ValueError, KeyError):
            continue
    
    return {"points": points, "raw_rows": len(rows), "time_is_pct": time_is_pct}


def parse_time_to_seconds(time_str: str) -> float:
    """Parse time string to seconds."""
    time_str = time_str.strip()
    if not time_str:
        return 0.0
    
    # HH:MM:SS
    if time_str.count(':') == 2:
        h, m, s = time_str.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    # MM:SS
    elif time_str.count(':') == 1:
        m, s = time_str.split(':')
        return int(m) * 60 + float(s)
    # Just seconds
    else:
        try:
            return float(time_str)
        except ValueError:
            return 0.0


def detect_hook_leak(points: List[Dict]) -> Dict:
    """Detect hook leak (first 30% of video or first 30 seconds)."""
    if not points:
        return {"leak_pct": 0, "severity": "unknown", "details": "No data", "start_retention": 0, "min_early_retention": 0}
    
    # Check if time is in percentage (0-100) or seconds
    time_is_pct = points[0].get("time_is_pct", False)
    
    if time_is_pct:
        # First 30% of video
        early_points = [p for p in points if p["time_seconds"] <= 30]
        time_unit = "%"
        time_desc = "30% of video"
    else:
        # First 30 seconds
        early_points = [p for p in points if p["time_seconds"] <= 30]
        time_unit = "s"
        time_desc = "30s"
    
    if not early_points:
        return {
            "leak_pct": 0, 
            "severity": "unknown", 
            "details": f"No early data (first {time_desc})",
            "start_retention": points[0]["retention_pct"] if points else 0,
            "min_early_retention": 0,
            "time_unit": time_unit,
            "time_desc": time_desc
        }
    
    start_retention = points[0]["retention_pct"] if points else 100
    min_early = min(p["retention_pct"] for p in early_points)
    leak = start_retention - min_early
    
    severity = "healthy" if leak < 25 else "moderate" if leak < 40 else "severe"
    
    return {
        "leak_pct": round(leak, 1),
        "severity": severity,
        "start_retention": start_retention,
        "min_early_retention": min_early,
        "time_unit": time_unit,
        "time_desc": time_desc,
        "details": f"Lost {leak:.1f}% in first {time_desc} ({severity})"
    }


def detect_cliffs(points: List[Dict], threshold: float = 5.0) -> List[Dict]:
    """Detect steep drops (cliffs) > threshold."""
    cliffs = []
    for i in range(1, len(points)):
        drop = points[i-1]["retention_pct"] - points[i]["retention_pct"]
        if drop >= threshold:
            cliffs.append({
                "time_seconds": points[i]["time_seconds"],
                "drop_pct": round(points[i-1]["retention_pct"] - points[i]["retention_pct"], 1),
                "before_pct": points[i-1]["retention_pct"],
                "after_pct": points[i]["retention_pct"],
            })
    return cliffs


def detect_slide(points: List[Dict], window: int = 30) -> Dict:
    """Detect steady bleed (slide) over windows."""
    if len(points) < 2:
        return {"slide_pct_per_min": 0, "severity": "unknown"}
    
    # Calculate average slope over sliding windows
    slopes = []
    for i in range(len(points) - 1):
        dt = points[i+1]["time_seconds"] - points[i]["time_seconds"]
        if dt <= 0:
            continue
        dpct = points[i]["retention_pct"] - points[i+1]["retention_pct"]
        slope = dpct / (dt / 60)  # % per minute
        slopes.append(slope)
    
    if not slopes:
        return {"slide_pct_per_min": 0, "severity": "unknown"}
    
    avg_slide = sum(slopes) / len(slopes)
    severity = "healthy" if avg_slide < 1 else "moderate" if avg_slide < 3 else "severe"
    
    return {
        "slide_pct_per_min": round(avg_slide, 2),
        "severity": severity,
        "details": f"Loses {avg_slide:.1f}% per minute on average ({severity})"
    }


def correlate_with_transcript(cliffs: List[Dict], transcript_path: str) -> List[Dict]:
    """Match cliffs to transcript segments."""
    if not cliffs or not transcript_path:
        return cliffs
    
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return cliffs
    
    transcript = transcript.get("transcript", transcript.get("transcripts", []))
    if isinstance(transcript, dict):
        transcript = transcript.get("transcript", [])
    
    # Build time-indexed transcript
    segments = []
    for seg in transcript:
        start = seg.get("start", 0)
        text = seg.get("text", "").strip()
        if text:
            segments.append((start, text))
    
    segments.sort(key=lambda x: x[0])
    
    # Match cliffs to nearest transcript segment
    for cliff in cliffs:
        t = cliff["time_seconds"]
        # Find segment active at cliff time
        for i, (start, text) in enumerate(segments):
            next_start = segments[i+1][0] if i+1 < len(segments) else float('inf')
            if start <= t < next_start:
                cliff["transcript_snippet"] = text[:200]
                break
    
    return cliffs


def main():
    parser = argparse.ArgumentParser(description="Analyze YouTube retention CSV")
    parser.add_argument("csv", help="Path to YouTube Studio audience-retention CSV export")
    parser.add_argument("--transcript", help="Optional transcript JSON to correlate cliffs")
    parser.add_argument("--threshold", type=float, default=5.0, help="Cliff detection threshold (% drop)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--duration", type=int, help="Video duration in seconds (converts % positions to seconds)")
    args = parser.parse_args()

    # Parse CSV
    data = parse_retention_csv(args.csv, video_duration_seconds=args.duration)
    if "error" in data:
        print(f"ERROR: {data['error']}", file=sys.stderr)
        sys.exit(1)
    
    points = data["points"]
    if not points:
        print("ERROR: No valid retention data points", file=sys.stderr)
        sys.exit(1)
    
    # Analyze
    hook = detect_hook_leak(points)
    cliffs = detect_cliffs(points, args.threshold)
    slide = detect_slide(points)
    
    # Correlate with transcript if provided
    if args.transcript:
        cliffs = correlate_with_transcript(cliffs, args.transcript)
    
    # Output
    result = {
        "hook_leak": hook,
        "cliffs": cliffs,
        "slide": slide,
        "summary": {
            "hook_severity": hook["severity"],
            "cliff_count": len(cliffs),
            "slide_severity": slide["severity"],
            "worst_cliff": max(cliffs, key=lambda c: c["drop_pct"]) if cliffs else None
        }
    }
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n=== RETENTION ANALYSIS ===")
        print(f"\n🔴 HOOK LEAK (first 30s): {hook['severity'].upper()}")
        print(f"   Lost {hook['leak_pct']:.1f}% (start: {hook['start_retention']:.1f}% → min: {hook['min_early_retention']:.1f}%)")
        print(f"   {hook['details']}")
        
        print(f"\n🟠 CLIFFS ({len(cliffs)} detected ≥{args.threshold:.1f}% drop):")
        for c in cliffs[:10]:
            mm, ss = divmod(int(c["time_seconds"]), 60)
            print(f"   {mm:02d}:{ss:02d}  Drop: {c['drop_pct']:.1f}%  ({c['before_pct']:.1f}% → {c['after_pct']:.1f}%)")
            if c.get("transcript_snippet"):
                print(f"      \"{c['transcript_snippet'][:80]}...\"")
        
        if len(cliffs) > 10:
            print(f"   ... and {len(cliffs)-10} more cliffs")
        
        print(f"\n🟡 SLIDE (steady bleed): {slide['severity'].upper()}")
        print(f"   {slide['details']}")
        
        if cliffs:
            worst = max(cliffs, key=lambda c: c["drop_pct"])
            print(f"\n🔴 WORST CLIFF: {worst['drop_pct']:.1f}% drop at {int(worst['time_seconds'])//60}:{int(worst['time_seconds'])%60:02d}")
            if worst.get("transcript_snippet"):
                print(f"   Context: \"{worst['transcript_snippet'][:100]}...\"")


if __name__ == "__main__":
    main()