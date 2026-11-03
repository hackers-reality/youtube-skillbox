#!/usr/bin/env python3
"""
YouTube Skillbox - CLI entry point.

This is a wrapper that imports the main ytdata module from the skills directory.
"""
import sys
import os

# Add the skills/youtube/scripts directory to the path
script_dir = os.path.dirname(os.path.abspath(__file__))
skills_dir = os.path.join(script_dir, "skills", "youtube", "scripts")
sys.path.insert(0, skills_dir)

# Import and run main
from ytdata import main as ytdata_main

if __name__ == "__main__":
    ytdata_main()