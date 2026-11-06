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
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime


_KNOWN_EXPORTS = {
    "All.csv": {
        "meaning": "Absolute audience retention, all viewers combined",
        "measures": "retention_curve_absolute",
        "can_infer_proportions": False,
        "warning": "Values >100% mean rewatches/loops; NOT a share of viewers",
    },
    "Detailed activity.csv": {
        "meaning": "Per-position watch/stop counts and moments-seen counts",
        "measures": "activity_counts",
        "can_infer_proportions": False,
        "warning": "Raw counts, not percentages of audience; good for locating drop-off positions",
    },
    "New and returning viewers.csv": {
        "meaning": "Retention curves split by viewer tenure (new vs returning)",
        "measures": "retention_curve_segmented",
        "can_infer_proportions": False,
        "warning": "Segmented retention curves, NOT the proportion of new vs returning viewers",
    },
    "New, casual and regular viewers.csv": {
        "meaning": "Retention curves by watch-behavior segment",
        "measures": "retention_curve_segmented",
        "can_infer_proportions": False,
        "warning": "Segmented curves by watch frequency; NOT audience-size shares",
    },
    "Subscribers and non-subscribers.csv": {
        "meaning": "Retention curves split by subscription status",
        "measures": "retention_curve_segmented",
        "can_infer_proportions": False,
        "warning": "Segmented retention, NOT the proportion of viewers who are subscribers",
    },
    "Organic and paid traffic.csv": {
        "meaning": "Retention by traffic source type (organic vs paid)",
        "measures": "retention_curve_by_source",
        "can_infer_proportions": False,
        "warning": "Retention by source; does NOT give overall share of organic vs paid traffic",
    },
    "Organic.csv": {
        "meaning": "Retention for organic traffic only",
        "measures": "retention_curve_by_source",
        "can_infer_proportions": False,
        "warning": "Organic-only retention curve; no paid comparison here",
    },
    "Skippable video ad.csv": {
        "meaning": "Retention for skippable ad views",
        "measures": "retention_curve_by_source",
        "can_infer_proportions": False,
        "warning": "Ad-view behavior; do not compare directly as organic performance",
    },
    "Video discovery ad.csv": {
        "meaning": "Retention for video discovery ad views",
        "measures": "retention_curve_by_source",
        "can_infer_proportions": False,
        "warning": "Ad-view behavior; do not compare directly as organic performance",
    },
}


def analyze_directory(dir_path: str) -> Dict:
    """Inventory every CSV in a YouTube Studio retention export and describe each.

    Never infers audience proportions, traffic shares or demographics unless the
    columns actually contain them; labels every dataset by what it measures.
    """
    p = Path(dir_path)
    if not p.is_dir():
        return {"error": f"Not a directory: {dir_path}"}
    found = sorted(p.glob("*.csv"))
    if not found:
        return {"error": f"No CSV files found in {dir_path}"}

    files = []
    for csv_file in found:
        key = csv_file.name
        try:
            with open(csv_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = [h.strip() for h in (reader.fieldnames or [])]
        except Exception as e:
            files.append({
                "file": key,
                "status": "unreadable",
                "error": str(e),
            })
            continue

        known = _KNOWN_EXPORTS.get(key)
        with open(csv_file, "r", encoding="utf-8-sig") as f:
            row_count = sum(1 for _ in f) - 1
        if known:
            files.append({
                "file": key,
                "status": "known",
                "meaning": known["meaning"],
                "measures": known["measures"],
                "can_infer_proportions": known["can_infer_proportions"],
                "interpretation_warning": known["warning"],
                "columns": headers,
                "rows": row_count,
            })
        else:
            files.append({
                "file": key,
                "status": "unclassified",
                "meaning": "Unrecognized YouTube Studio export",
                "measures": "unknown",
                "can_infer_proportions": False,
                "interpretation_warning": "Do NOT interpret this file until its columns are inspected manually",
                "columns": headers,
                "rows": row_count,
            })

    data_out = {
        "directory": str(p.resolve()),
        "files_found": len(found),
        "files": files,
        "global_warning": (
            "These CSVs are segmented retention/activity curves. None of them, by itself, "
            "proves audience proportions (e.g. '% of viewers who are subscribers'), traffic shares, "
            "or demographics unless the columns explicitly contain those measures."
        ),
    }
    return data_out


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
    
    # Column unit decides meaning: "Video position (%)" (normalized: *_pct)
    # is a percent axis; "Elapsed time" is literal seconds (plain numbers or clocks).
    # This is what stops "30" from being ambiguous between 30% and 30s.
    position_is_pct = "pct" in time_col.lower()

    # Parse data points
    points = []
    original_time_is_pct = False  # Track original format before conversion
    for row in rows:
        try:
            time_val = row[time_col]
            # Check if time is in HH:MM:SS format or plain number
            if ':' in str(time_val):
                seconds = parse_time_to_seconds(time_val)
                pct = (seconds / video_duration_seconds * 100.0) if video_duration_seconds else None
                original_time_is_pct = False
            elif position_is_pct:
                # Percent of video (0-100) - convert to seconds if duration known
                try:
                    pct = float(time_val)
                    original_time_is_pct = True
                    if video_duration_seconds:
                        seconds = (pct / 100.0) * video_duration_seconds
                    else:
                        seconds = None  # PERCENT-only: do NOT fake 100s scale
                except ValueError:
                    continue
            else:
                # Elapsed-time column: plain numbers are seconds, not percents.
                try:
                    seconds = float(time_val)
                    pct = (seconds / video_duration_seconds * 100.0) if video_duration_seconds else None
                    original_time_is_pct = False
                except ValueError:
                    continue
            retention = float(row[retention_col].replace('%', '').replace(',', ''))
            points.append({
                "time_seconds": seconds,
                "time_pct": pct,
                "retention_pct": retention,
                "original_time_is_pct": original_time_is_pct,
            })
        except (ValueError, KeyError):
            continue
    
    return {
        "points": points,
        "raw_rows": len(rows),
        "original_time_is_pct": original_time_is_pct,
        "video_duration_seconds": video_duration_seconds,
    }


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


def _is_absolute_retention(points: List[Dict]) -> bool:
    """Absolute audience retention can exceed 100% (loops/replays). Relative retention never does."""
    return any(p.get("retention_pct", 0) > 100 for p in points)


def detect_hook_leak(points: List[Dict]) -> Dict:
    """Detect hook leak (first 30% of video or first 30 seconds)."""
    if not points:
        return {"leak_pct": 0, "severity": "unknown", "details": "No data", "start_retention": 0, "min_early_retention": 0, "time_unit": "s", "time_desc": "30s"}
    # Check if time is in percentage (0-100) or seconds
    # Use original_time_is_pct to determine the original unit
    time_is_pct = points[0].get("original_time_is_pct", False)
    
    if time_is_pct:
        # First 30% of video (percentage axis — no fake seconds).
        # Legacy points built without time_pct carry the percent in time_seconds.
        early_points = [p for p in points
                        if (p.get("time_pct") if p.get("time_pct") is not None
                            else p.get("time_seconds")) is not None
                        and (p.get("time_pct") if p.get("time_pct") is not None
                             else p.get("time_seconds")) <= 30]
        time_unit = "%"
        time_desc = "30% of video"
    else:
        # First 30 seconds
        early_points = [p for p in points if (p.get("time_seconds") is not None and p["time_seconds"] <= 30)]
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

    absolute = _is_absolute_retention(early_points)
    severity = "n/a (absolute retention)" if absolute else (
        "healthy" if leak < 25 else "moderate" if leak < 40 else "severe")

    return {
        "leak_pct": round(leak, 1),
        "severity": severity,
        "start_retention": start_retention,
        "min_early_retention": min_early,
        "absolute_retention": absolute,
        "time_unit": time_unit,
        "time_desc": time_desc,
        "details": (f"Absolute audience retention (values >100% = loops/replays); cliff drops below are meaningful, but leak/slide ratios are not. "
                    f"Lost {leak:.1f}% in first {time_desc} ({severity})") if absolute else
                   f"Lost {leak:.1f}% in first {time_desc} ({severity})"
    }


def detect_cliffs(points: List[Dict], threshold: float = 5.0) -> List[Dict]:
    """Detect steep drops (cliffs) > threshold. Reports BOTH axes honestly:
    time_pct is always defined for pct CSVs; time_seconds is None unless the
    caller passed --duration (never a fake 100s scale)."""
    cliffs = []
    for i in range(1, len(points)):
        drop = points[i-1]["retention_pct"] - points[i]["retention_pct"]
        if drop >= threshold:
            cliffs.append({
                "time_seconds": points[i].get("time_seconds"),
                "time_pct": points[i].get("time_pct"),
                "time_unit": "s" if points[i].get("time_seconds") is not None else "%",
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
        t0, t1 = points[i].get("time_seconds"), points[i+1].get("time_seconds")
        if t0 is None or t1 is None:
            continue  # percent-only axis: %/minute is undefined — report n/a below
        dt = t1 - t0
        if dt <= 0:
            continue
        dpct = points[i]["retention_pct"] - points[i+1]["retention_pct"]
        slope = dpct / (dt / 60)  # % per minute
        slopes.append(slope)
    
    if not slopes:
        return {"slide_pct_per_min": 0, "severity": "n/a (percent-only axis — pass --duration)",
                "absolute_retention": _is_absolute_retention(points),
                "details": "Slide per minute needs --duration to convert % axis to seconds; passing --duration <seconds> from the video metadata unlocks it."}
    
    avg_slide = sum(slopes) / len(slopes)
    absolute = _is_absolute_retention(points)
    severity = "n/a (absolute retention)" if absolute else (
        "healthy" if avg_slide < 1 else "moderate" if avg_slide < 3 else "severe")

    return {
        "slide_pct_per_min": round(avg_slide, 2),
        "severity": severity,
        "absolute_retention": absolute,
        "details": (f"Absolute audience retention (values >100% = loops/replays); slide rate not meaningful. "
                    f"Loses {avg_slide:.1f}% per minute on average ({severity})") if absolute else
                   f"Loses {avg_slide:.1f}% per minute on average ({severity})"
    }


def correlate_with_transcript(cliffs: List[Dict], transcript_path: str) -> List[Dict]:
    """Match cliffs to transcript segments."""
    if not cliffs or not transcript_path:
        return cliffs
    
    try:
        with open(transcript_path, 'r', encoding='utf-8-sig') as f:
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
    
    # Match cliffs to nearest transcript segment (seconds axis ONLY —
    # a percent-axis cliff cannot be matched to transcript timestamps)
    for cliff in cliffs:
        t = cliff.get("time_seconds")
        if t is None:
            continue
        # Find segment active at cliff time
        for i, (start, text) in enumerate(segments):
            next_start = segments[i+1][0] if i+1 < len(segments) else float('inf')
            if start <= t < next_start:
                cliff["transcript_snippet"] = text[:200]
                break
    
    return cliffs


def main():
    parser = argparse.ArgumentParser(description="Analyze YouTube retention CSV or a Studio export directory")
    parser.add_argument("csv", help="Path to a CSV file OR a directory containing YouTube Studio retention CSVs (use --dir mode for exports)")
    parser.add_argument("--dir", action="store_true", help="Interpret the path as an export DIRECTORY and inventory every CSV found (never reads only All.csv)")
    parser.add_argument("--transcript", help="Optional transcript JSON to correlate cliffs")
    parser.add_argument("--threshold", type=float, default=5.0, help="Cliff detection threshold (percent drop)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--duration", type=int,
                        help="Video duration in seconds (converts % positions to seconds). "
                             "Get it from the video metadata (ytdata info duration_seconds / "
                             "transcript metadata duration_seconds). WITHOUT it, timings are "
                             "reported as percentages ONLY — never as seconds.")
    args = parser.parse_args()

    # Directory mode: inventory the Studio export rather than relying on All.csv alone
    if args.dir or os.path.isdir(args.csv):
        data = analyze_directory(args.csv)
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return
        if "error" in data:
            print(f"ERROR: {data['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"\n=== RETENTION EXPORT INVENTORY ({data['files_found']} CSV files) ===")
        for f in data["files"]:
            status = f["status"].upper()
            print(f"\n{status}  {f['file']}")
            print(f"        measures : {f.get('measures', 'unknown')}")
            print(f"        meaning  : {f.get('meaning', 'unknown')}")
            print(f"        columns  : {', '.join(f.get('columns', []))}")
            if f.get("interpretation_warning"):
                print(f"        warning  : {f['interpretation_warning']}")
        print(f"\nGLOBAL WARNING: {data['global_warning']}")
        return

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
        "video_duration_seconds": args.duration,
        "timing_basis": ("seconds (--duration)" if args.duration
                         else "percent ONLY (no --duration — pass the video's actual duration)"),
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
    if data.get("original_time_is_pct") and not args.duration:
        result["warning"] = ("Timing axis is PERCENT (0-100), not seconds. "
                             "Cliff positions are percentages. Re-run with --duration <seconds> "
                             "(actual video duration) for literal timestamps.")
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n=== RETENTION ANALYSIS ===")
        print(f"\n🔴 HOOK LEAK (first 30s): {hook['severity'].upper()}")
        print(f"   Lost {hook['leak_pct']:.1f}% (start: {hook['start_retention']:.1f}% → min: {hook['min_early_retention']:.1f}%)")
        print(f"   {hook['details']}")
        
        print(f"\n🟠 CLIFFS ({len(cliffs)} detected ≥{args.threshold:.1f}% drop, axis: {result['timing_basis']}):")
        for c in cliffs[:10]:
            if c.get("time_seconds") is not None:
                mm, ss = divmod(int(c["time_seconds"]), 60)
                when = f"{mm:02d}:{ss:02d}"
            else:
                when = f"{c.get('time_pct'):.0f}% of video"
            print(f"   {when}  Drop: {c['drop_pct']:.1f}%  ({c['before_pct']:.1f}% → {c['after_pct']:.1f}%)")
            if c.get("transcript_snippet"):
                print(f"      \"{c['transcript_snippet'][:80]}...\"")
        
        if len(cliffs) > 10:
            print(f"   ... and {len(cliffs)-10} more cliffs")
        
        print(f"\n🟡 SLIDE (steady bleed): {slide['severity'].upper()}")
        print(f"   {slide['details']}")
        
        if cliffs:
            worst = max(cliffs, key=lambda c: c["drop_pct"])
            if worst.get("time_seconds") is not None:
                when = f"{int(worst['time_seconds'])//60}:{int(worst['time_seconds'])%60:02d}"
            else:
                when = f"{worst.get('time_pct'):.0f}% of video (percent axis)"
            print(f"\n🔴 WORST CLIFF: {worst['drop_pct']:.1f}% drop at {when}")
            if worst.get("transcript_snippet"):
                print(f"   Context: \"{worst['transcript_snippet'][:100]}...\"")


if __name__ == "__main__":
    main()