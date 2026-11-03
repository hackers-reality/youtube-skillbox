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