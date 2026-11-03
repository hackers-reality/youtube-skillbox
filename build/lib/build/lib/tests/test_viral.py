#!/usr/bin/env python3
"""
Tests for skills/yt-viral/scripts/viral.py

Covers:
- Channel stats parsing
- Video fetching
- Outlier analysis
- Velocity analysis
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "yt-viral", "scripts"))
import viral


class TestRunYtdlp(unittest.TestCase):
    """Test run_ytdlp wrapper."""

    @patch("viral.subprocess.run")
    def test_run_ytdlp_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"id": "test"}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = viral.run_ytdlp(["--skip-download", "--dump-single-json", "url"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '{"id": "test"}')

    @patch("viral.subprocess.run")
    def test_run_ytdlp_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "ERROR: Not found"
        mock_run.return_value = mock_result

        result = viral.run_ytdlp(["--skip-download", "--dump-single-json", "url"])
        self.assertEqual(result.returncode, 1)


class TestGetChannelStats(unittest.TestCase):
    """Test get_channel_stats function."""

    @patch("viral.run_ytdlp")
    def test_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "channel": "Test Channel",
            "id": "@testchannel",
            "webpage_url": "https://www.youtube.com/@testchannel",
            "channel_follower_count": 1000,
            "view_count": 50000,
            "playlist_count": 20
        })
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = viral.get_channel_stats("@testchannel")
        self.assertEqual(result["channel"], "Test Channel")
        self.assertEqual(result["handle"], "@testchannel")
        self.assertEqual(result["subscribers"], 1000)
        self.assertEqual(result["total_views"], 50000)
        self.assertEqual(result["video_count"], 20)

    @patch("viral.run_ytdlp")
    def test_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "ERROR"
        mock_run.return_value = mock_result

        result = viral.get_channel_stats("@testchannel")
        self.assertEqual(result, {})


class TestGetVideos(unittest.TestCase):
    """Test get_videos function."""

    @patch("viral.run_ytdlp")
    def test_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '\n'.join([
            '{"id": "vid1", "title": "Video 1", "view_count": 1000}',
            '{"id": "vid2", "title": "Video 2", "view_count": 2000}',
            'invalid json line',
        ])
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        videos = viral.get_videos("@testchannel", limit=10, tab="videos")
        self.assertEqual(len(videos), 2)
        self.assertEqual(videos[0]["id"], "vid1")
        self.assertEqual(videos[0]["title"], "Video 1")
        self.assertEqual(videos[0]["view_count"], 1000)

    @patch("viral.run_ytdlp")
    def test_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "ERROR"
        mock_run.return_value = mock_result

        videos = viral.get_videos("@testchannel", limit=10, tab="videos")
        self.assertEqual(videos, [])


class TestGetVideoDetails(unittest.TestCase):
    """Test get_video_details function."""

    @patch("viral.run_ytdlp")
    def test_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "id": "vid1",
            "title": "Test Video",
            "view_count": 5000,
            "upload_date": "20240115",
            "duration": 300
        })
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = viral.get_video_details("vid1")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "vid1")
        self.assertEqual(result["view_count"], 5000)

    @patch("viral.run_ytdlp")
    def test_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "ERROR"
        mock_run.return_value = mock_result

        result = viral.get_video_details("vid1")
        self.assertIsNone(result)


class TestParseUploadDate(unittest.TestCase):
    """Test parse_upload_date function."""

    def test_valid_yyyymmdd(self):
        result = viral.parse_upload_date("20240115")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_invalid_formats(self):
        self.assertIsNone(viral.parse_upload_date(""))
        self.assertIsNone(viral.parse_upload_date("2024"))
        self.assertIsNone(viral.parse_upload_date("202401"))
        self.assertIsNone(viral.parse_upload_date("not_a_date"))
        self.assertIsNone(viral.parse_upload_date("2024-01-15"))


class TestCalculateVph(unittest.TestCase):
    """Test calculate_vph function."""

    def test_valid_calculation(self):
        # 1000 views over 10 hours = 100 vph
        result = viral.calculate_vph(1000, "20240115")
        # We can't easily test exact value without mocking datetime.now
        # but we can verify it returns a float >= 0
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0)

    def test_zero_views(self):
        result = viral.calculate_vph(0, "20240115")
        self.assertEqual(result, 0.0)

    def test_missing_date(self):
        result = viral.calculate_vph(1000, "")
        self.assertEqual(result, 0.0)

    def test_future_date(self):
        # If upload date is in the future, hours <= 0, should return view_count
        from datetime import datetime, timedelta
        future = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        result = viral.calculate_vph(1000, future)
        # hours <= 0 returns float(view_count)
        self.assertEqual(result, float(1000))


class TestAnalyzeOutliers(unittest.TestCase):
    """Test analyze_outliers function."""

    @patch("viral.get_video_details")
    def test_outliers_found(self, mock_get_details):
        channel_stats = {"subscribers": 1000}
        videos = [
            {"id": "vid1", "view_count": 5000},
            {"id": "vid2", "view_count": 1000},
            {"id": "vid3", "view_count": 100},  # 0.1x ratio - below default 2.0 threshold
        ]
        
        # Mock get_video_details to return details for each video
        def mock_details(vid):
            if vid == "vid1":
                return {"view_count": 5000, "title": "Video 1", "upload_date": "20240115", "duration": 300, "tags": []}
            elif vid == "vid2":
                return {"view_count": 1000, "title": "Video 2", "upload_date": "20240115", "duration": 300, "tags": []}
            elif vid == "vid3":
                return {"view_count": 100, "title": "Video 3", "upload_date": "20240115", "duration": 300, "tags": []}
            return None
        
        mock_get_details.side_effect = mock_details

        outliers = viral.analyze_outliers(channel_stats, videos, min_ratio=2.0)
        
        # vid1: 5000/1000 = 5.0x (outlier)
        # vid2: 1000/1000 = 1.0x (not outlier at 2.0)
        # vid3: 100/1000 = 0.1x (not outlier)
        self.assertEqual(len(outliers), 1)
        self.assertEqual(outliers[0]["video_id"], "vid1")
        self.assertEqual(outliers[0]["ratio"], 5.0)

    @patch("viral.get_video_details")
    def test_no_subscribers(self, mock_get_details):
        channel_stats = {"subscribers": 0}
        videos = [{"id": "vid1", "view_count": 1000}]
        
        outliers = viral.analyze_outliers(channel_stats, videos, min_ratio=2.0)
        self.assertEqual(outliers, [])

    @patch("viral.get_video_details")
    def test_sorting_by_ratio(self, mock_get_details):
        channel_stats = {"subscribers": 1000}
        videos = [
            {"id": "vid1", "view_count": 2000},
            {"id": "vid2", "view_count": 5000},
            {"id": "vid3", "view_count": 3000},
        ]
        
        def mock_details(vid):
            views = {"vid1": 2000, "vid2": 5000, "vid3": 3000}[vid]
            return {"view_count": views, "title": f"Video {vid}", "upload_date": "20240115", "duration": 300, "tags": []}
        
        mock_get_details.side_effect = mock_details

        outliers = viral.analyze_outliers(channel_stats, videos, min_ratio=1.0)
        # Should be sorted by ratio descending: 5.0, 3.0, 2.0
        self.assertEqual(len(outliers), 3)
        self.assertEqual(outliers[0]["video_id"], "vid2")
        self.assertEqual(outliers[1]["video_id"], "vid3")
        self.assertEqual(outliers[2]["video_id"], "vid1")


class TestAnalyzeVelocity(unittest.TestCase):
    """Test analyze_velocity function."""

    @patch("viral.get_video_details")
    def test_velocity_calculation(self, mock_get_details):
        videos = [
            {"id": "vid1", "view_count": 1000},
            {"id": "vid2", "view_count": 2000},
        ]
        
        def mock_details(vid):
            if vid == "vid1":
                return {"view_count": 1000, "title": "Video 1", "upload_date": "20240101"}
            elif vid == "vid2":
                return {"view_count": 2000, "title": "Video 2", "upload_date": "20240101"}
            return None
        
        mock_get_details.side_effect = mock_details

        velocity = viral.analyze_velocity(videos, top_n=10)
        
        # Both should have velocity calculated
        self.assertEqual(len(velocity), 2)
        for v in velocity:
            self.assertIn("vph", v)
            self.assertIn("video_id", v)
            self.assertIn("views", v)

    @patch("viral.get_video_details")
    def test_top_n_limit(self, mock_get_details):
        videos = [{"id": f"vid{i}", "view_count": 1000} for i in range(15)]
        
        def mock_details(vid):
            return {"view_count": 1000, "title": vid, "upload_date": "20240101"}
        
        mock_get_details.side_effect = mock_details

        velocity = viral.analyze_velocity(videos, top_n=5)
        self.assertEqual(len(velocity), 5)


class TestMainArgumentParsing(unittest.TestCase):
    """Test main() argument parsing."""

    def test_argument_parser_exists(self):
        """Verify argument parser is configured."""
        # Just verify the module has the expected structure
        self.assertTrue(hasattr(viral, "main"))
        self.assertTrue(callable(viral.main))


if __name__ == "__main__":
    unittest.main()