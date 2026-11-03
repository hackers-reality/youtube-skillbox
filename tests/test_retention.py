#!/usr/bin/env python3
"""
Tests for skills/yt-retention/scripts/retention.py

Covers:
- Percentage positions with --duration (converts to seconds)
- Percentage positions without --duration (keeps as percentage)
- Seconds-based positions (HH:MM:SS, MM:SS)
- Missing early data (no points in hook window)
- Invalid or empty CSV
- Custom cliff thresholds
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "yt-retention", "scripts"))
import retention


class TestParseRetentionCSV(unittest.TestCase):
    """Test parse_retention_csv function."""

    def create_csv_content(self, header, rows):
        """Helper to create CSV content."""
        lines = [header] + [",".join(row) for row in rows]
        return "\n".join(lines)

    def test_percentage_position_with_duration(self):
        """Percentage positions should convert to seconds when --duration provided."""
        csv_content = self.create_csv_content(
            "Video position (%),Absolute audience retention (%)",
            [["0", "100"], ["50", "50"], ["100", "0"]]
        )
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv", video_duration_seconds=60)
        
        self.assertFalse(result.get("error"))
        points = result["points"]
        self.assertEqual(len(points), 3)
        # 0% -> 0s, 50% -> 30s, 100% -> 60s
        self.assertEqual(points[0]["time_seconds"], 0)
        self.assertEqual(points[1]["time_seconds"], 30)
        self.assertEqual(points[2]["time_seconds"], 60)
        self.assertTrue(points[0].get("time_is_pct", False))

    def test_percentage_position_without_duration(self):
        """Percentage positions should stay as percentages when no --duration."""
        csv_content = self.create_csv_content(
            "Video position (%),Absolute audience retention (%)",
            [["0", "100"], ["50", "50"], ["100", "0"]]
        )
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv", video_duration_seconds=None)
        
        self.assertFalse(result.get("error"))
        points = result["points"]
        self.assertEqual(len(points), 3)
        # Should remain as percentages
        self.assertEqual(points[0]["time_seconds"], 0)
        self.assertEqual(points[1]["time_seconds"], 50)
        self.assertEqual(points[2]["time_seconds"], 100)
        self.assertTrue(points[0].get("time_is_pct", False))

    def test_seconds_based_positions_hhmmss(self):
        """HH:MM:SS format should parse to seconds."""
        csv_content = self.create_csv_content(
            "Elapsed time,Absolute audience retention (%)",
            [["00:00:00", "100"], ["00:00:30", "80"], ["00:01:00", "60"]]
        )
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv", video_duration_seconds=None)
        
        self.assertFalse(result.get("error"))
        points = result["points"]
        self.assertEqual(len(points), 3)
        self.assertEqual(points[0]["time_seconds"], 0)
        self.assertEqual(points[1]["time_seconds"], 30)
        self.assertEqual(points[2]["time_seconds"], 60)
        self.assertFalse(points[0].get("time_is_pct", True))

    def test_seconds_based_positions_mmss(self):
        """MM:SS format should parse to seconds."""
        csv_content = self.create_csv_content(
            "Elapsed time,Absolute audience retention (%)",
            [["0:00", "100"], ["0:30", "80"], ["1:00", "60"]]
        )
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv", video_duration_seconds=None)
        
        points = result["points"]
        self.assertEqual(points[0]["time_seconds"], 0)
        self.assertEqual(points[1]["time_seconds"], 30)
        self.assertEqual(points[2]["time_seconds"], 60)

    def test_seconds_only(self):
        """Plain seconds should parse correctly."""
        csv_content = self.create_csv_content(
            "Elapsed time,Absolute audience retention (%)",
            [["0", "100"], ["30", "80"], ["60", "60"]]
        )
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv", video_duration_seconds=None)
        
        points = result["points"]
        self.assertEqual(points[0]["time_seconds"], 0)
        self.assertEqual(points[1]["time_seconds"], 30)
        self.assertEqual(points[2]["time_seconds"], 60)

    def test_missing_early_data(self):
        """Hook leak detection should handle missing early points."""
        # No points in first 30% (for percentage) or 30s (for seconds)
        # Using 60% (36s) and 100% (60s) - both > 30s
        csv_content = self.create_csv_content(
            "Video position (%),Absolute audience retention (%)",
            [["60", "50"], ["100", "0"]]  # No point <= 30s
        )
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv", video_duration_seconds=60)
        
        points = result["points"]
        # Points at 60% (36s) and 100% (60s) - no early data for hook leak
        # detect_hook_leak should return unknown with start_retention from first point
        hook = retention.detect_hook_leak(points)
        self.assertEqual(hook["severity"], "unknown")
        self.assertIn("No early data", hook["details"])
        # Should still have start_retention from first available point
        self.assertEqual(hook["start_retention"], 50)

    def test_empty_csv(self):
        """Empty CSV should return error."""
        csv_content = "Video position (%),Absolute audience retention (%)"
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv")
        
        self.assertIn("error", result)

    def test_invalid_values(self):
        """Invalid numeric values should be skipped gracefully."""
        csv_content = self.create_csv_content(
            "Video position (%),Absolute audience retention (%)",
            [["0", "100"], ["invalid", "50"], ["50", "not_a_number"]]
        )
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv")
        
        points = result["points"]
        # Should only have the valid row
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["time_seconds"], 0)
        self.assertEqual(points[0]["retention_pct"], 100)

    def test_column_detection_video_position_pct(self):
        """Should correctly detect 'Video position (%)' column."""
        csv_content = self.create_csv_content(
            "Video position (%),Absolute audience retention (%)",
            [["0", "100"], ["50", "50"]]
        )
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv")
        
        self.assertFalse(result.get("error"))
        self.assertEqual(len(result["points"]), 2)

    def test_column_detection_elapsed_time(self):
        """Should correctly detect 'Elapsed time' column."""
        csv_content = self.create_csv_content(
            "Elapsed time,Absolute audience retention (%)",
            [["0:00", "100"], ["0:30", "50"]]
        )
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv")
        
        self.assertFalse(result.get("error"))
        self.assertEqual(len(result["points"]), 2)

    def test_avoids_wrong_pct_columns(self):
        """Should not pick up unrelated percentage columns."""
        # Multiple % columns - should pick the right ones
        csv_content = self.create_csv_content(
            "Video position (%),Some other %,Absolute audience retention (%)",
            [["0", "10", "100"], ["50", "20", "50"]]
        )
        
        with patch("builtins.open", mock_open(read_data=csv_content)):
            result = retention.parse_retention_csv("fake.csv")
        
        self.assertFalse(result.get("error"))
        self.assertEqual(len(result["points"]), 2)
        # Should use "Video position (%)" not "Some other %"


class TestDetectHookLeak(unittest.TestCase):
    """Test detect_hook_leak function."""

    def test_percentage_mode(self):
        """Hook leak with percentage positions (first 30%)."""
        points = [
            {"time_seconds": 0, "retention_pct": 100, "time_is_pct": True},
            {"time_seconds": 10, "retention_pct": 80, "time_is_pct": True},
            {"time_seconds": 30, "retention_pct": 70, "time_is_pct": True},
            {"time_seconds": 50, "retention_pct": 60, "time_is_pct": True},
        ]
        result = retention.detect_hook_leak(points)
        self.assertEqual(result["time_unit"], "%")
        self.assertEqual(result["time_desc"], "30% of video")
        # Lost 30% (100 -> 70) in first 30%
        self.assertEqual(result["leak_pct"], 30)
        self.assertEqual(result["severity"], "moderate")

    def test_seconds_mode(self):
        """Hook leak with seconds (first 30s)."""
        points = [
            {"time_seconds": 0, "retention_pct": 100, "time_is_pct": False},
            {"time_seconds": 10, "retention_pct": 80, "time_is_pct": False},
            {"time_seconds": 30, "retention_pct": 70, "time_is_pct": False},
        ]
        result = retention.detect_hook_leak(points)
        self.assertEqual(result["time_unit"], "s")
        self.assertEqual(result["time_desc"], "30s")
        self.assertEqual(result["leak_pct"], 30)

    def test_no_early_data_percentage(self):
        """No points in first 30% should return unknown."""
        points = [
            {"time_seconds": 50, "retention_pct": 50, "time_is_pct": True},
            {"time_seconds": 100, "retention_pct": 30, "time_is_pct": True},
        ]
        result = retention.detect_hook_leak(points)
        self.assertEqual(result["severity"], "unknown")
        self.assertIn("No early data", result["details"])

    def test_no_early_data_seconds(self):
        """No points in first 30s should return unknown."""
        points = [
            {"time_seconds": 40, "retention_pct": 50, "time_is_pct": False},
            {"time_seconds": 60, "retention_pct": 30, "time_is_pct": False},
        ]
        result = retention.detect_hook_leak(points)
        self.assertEqual(result["severity"], "unknown")

    def test_empty_points(self):
        """Empty points should return unknown with zero values."""
        result = retention.detect_hook_leak([])
        self.assertEqual(result["severity"], "unknown")
        self.assertEqual(result["leak_pct"], 0)
        self.assertEqual(result["start_retention"], 0)
        self.assertEqual(result["min_early_retention"], 0)


class TestDetectCliffs(unittest.TestCase):
    """Test detect_cliffs function."""

    def test_custom_threshold(self):
        """Should respect custom threshold argument."""
        points = [
            {"time_seconds": 0, "retention_pct": 100},
            {"time_seconds": 10, "retention_pct": 94},  # 6% drop
            {"time_seconds": 20, "retention_pct": 88},  # 6% drop
            {"time_seconds": 30, "retention_pct": 82},  # 6% drop
        ]
        # Default threshold 5% - should detect all three
        cliffs = retention.detect_cliffs(points, threshold=5.0)
        self.assertEqual(len(cliffs), 3)
        
        # Threshold 7% - should detect none
        cliffs = retention.detect_cliffs(points, threshold=7.0)
        self.assertEqual(len(cliffs), 0)

    def test_cliff_structure(self):
        """Cliff objects should have correct structure."""
        points = [
            {"time_seconds": 0, "retention_pct": 100},
            {"time_seconds": 10, "retention_pct": 80},  # 20% drop
        ]
        cliffs = retention.detect_cliffs(points, threshold=5.0)
        self.assertEqual(len(cliffs), 1)
        cliff = cliffs[0]
        self.assertIn("time_seconds", cliff)
        self.assertIn("drop_pct", cliff)
        self.assertIn("before_pct", cliff)
        self.assertIn("after_pct", cliff)
        self.assertEqual(cliff["drop_pct"], 20)


class TestDetectSlide(unittest.TestCase):
    """Test detect_slide function."""

    def test_healthy_slide(self):
        """Low slide rate should be healthy (< 1%/min)."""
        points = [
            {"time_seconds": 0, "retention_pct": 100},
            {"time_seconds": 120, "retention_pct": 99},  # 0.5%/min
            {"time_seconds": 240, "retention_pct": 98},  # 0.5%/min
        ]
        result = retention.detect_slide(points)
        self.assertEqual(result["severity"], "healthy")

    def test_moderate_slide(self):
        """Moderate slide rate (1-3%/min)."""
        points = [
            {"time_seconds": 0, "retention_pct": 100},
            {"time_seconds": 60, "retention_pct": 98},  # 2%/min
            {"time_seconds": 120, "retention_pct": 96},  # 2%/min
        ]
        result = retention.detect_slide(points)
        self.assertEqual(result["severity"], "moderate")

    def test_severe_slide(self):
        """Severe slide rate (> 3%/min)."""
        points = [
            {"time_seconds": 0, "retention_pct": 100},
            {"time_seconds": 60, "retention_pct": 70},  # 30%/min
        ]
        result = retention.detect_slide(points)
        self.assertEqual(result["severity"], "severe")


class TestParseTimeToSeconds(unittest.TestCase):
    """Test parse_time_to_seconds function."""

    def test_hhmmss(self):
        self.assertEqual(retention.parse_time_to_seconds("01:30:45"), 5445)

    def test_mmss(self):
        self.assertEqual(retention.parse_time_to_seconds("30:45"), 1845)

    def test_seconds_only(self):
        self.assertEqual(retention.parse_time_to_seconds("45"), 45)

    def test_empty_and_invalid(self):
        self.assertEqual(retention.parse_time_to_seconds(""), 0)
        self.assertEqual(retention.parse_time_to_seconds("invalid"), 0)


if __name__ == "__main__":
    unittest.main()