#!/usr/bin/env python3
"""
YouTube Skillbox - CLI entry point.
"""
import sys
import os
import argparse

# Get version from package metadata
def get_version():
    try:
        from importlib.metadata import version
        return version("youtube-skillbox")
    except Exception:
        return "unknown"

# Find the skills directory from the installed package
def find_skills_dir():
    """Find the skills/youtube/scripts directory from the installed package."""
    try:
        import youtube_skillbox
        pkg_path = os.path.dirname(youtube_skillbox.__file__)
        skills_dir = os.path.join(pkg_path, "skills", "youtube", "scripts")
        if os.path.isdir(skills_dir):
            return skills_dir
    except ImportError:
        pass
    # Fallback: try relative to this file (editable install from source)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    skills_dir = os.path.join(repo_root, "skills", "youtube", "scripts")
    if os.path.isdir(skills_dir):
        return skills_dir
    raise RuntimeError("Could not locate skills/youtube/scripts directory")

def get_version():
    try:
        from importlib.metadata import version
        return version("youtube-skillbox")
    except Exception:
        return "unknown"

# Find the skills directory from the installed package
def find_skills_dir():
    """Find the skills/youtube/scripts directory from the installed package."""
    try:
        import youtube_skillbox
        pkg_path = os.path.dirname(youtube_skillbox.__file__)
        skills_dir = os.path.join(pkg_path, "skills", "youtube", "scripts")
        if os.path.isdir(skills_dir):
            return skills_dir
    except ImportError:
        pass
    # Fallback: try relative to this file (editable install from source)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    skills_dir = os.path.join(repo_root, "skills", "youtube", "scripts")
    if os.path.isdir(skills_dir):
        return skills_dir
    raise RuntimeError("Could not locate skills/youtube/scripts directory")

def main():
    # Handle version flag early
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"ytdata {get_version()}")
        return
    
    # Check if a subcommand is provided (first arg after program name)
    # Known subcommands
    subcommands = {
        "search", "channel", "latest", "playlist", "profile", "posts",
        "sections", "shows", "home", "info", "scorecard", "outliers",
        "gap", "keywords", "compete", "trends", "track"
    }
    
    # Check if first arg after program name is a subcommand
    has_subcommand = len(sys.argv) > 1 and sys.argv[1] in subcommands
    
    # Show help only if no subcommand and help requested
    if ("--help" in sys.argv or "-h" in sys.argv) and not has_subcommand:
        parser = argparse.ArgumentParser(
            prog="ytdata",
            description="YouTube research via yt-dlp (no API key)",
        )
        parser.print_help()
        return
    
    # Pass all args to ytdata
    skills_dir = find_skills_dir()
    sys.path.insert(0, skills_dir)
    
    from ytdata import main
    main()

def get_version():
    try:
        from importlib.metadata import version
        return version("youtube-skillbox")
    except Exception:
        return "unknown"

# Find the skills directory from the installed package
def find_skills_dir():
    """Find the skills/youtube/scripts directory from the installed package."""
    try:
        import youtube_skillbox
        pkg_path = os.path.dirname(youtube_skillbox.__file__)
        skills_dir = os.path.join(pkg_path, "skills", "youtube", "scripts")
        if os.path.isdir(skills_dir):
            return skills_dir
    except ImportError:
        pass
    # Fallback: try relative to this file (editable install from source)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    skills_dir = os.path.join(repo_root, "skills", "youtube", "scripts")
    if os.path.isdir(skills_dir):
        return skills_dir
    raise RuntimeError("Could not locate skills/youtube/scripts directory")

def main():
    # Handle version flag early
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"ytdata {get_version()}")
        return
    
    # Check if a subcommand is provided (first arg after program name)
    # Known subcommands
    subcommands = {
        "search", "channel", "latest", "playlist", "profile", "posts",
        "sections", "shows", "home", "info", "scorecard", "outliers",
        "gap", "keywords", "compete", "trends", "track"
    }
    
    # Check if first arg after program name is a subcommand
    has_subcommand = len(sys.argv) > 1 and sys.argv[1] in subcommands
    
    # Show help only if no subcommand and help requested
    if ("--help" in sys.argv or "-h" in sys.argv) and not has_subcommand:
        parser = argparse.ArgumentParser(
            prog="ytdata",
            description="YouTube research via yt-dlp (no API key)",
        )
        parser.print_help()
        return
    
    # Pass all args to ytdata
    skills_dir = find_skills_dir()
    sys.path.insert(0, skills_dir)
    
    from ytdata import main
    main()

def get_version():
    try:
        from importlib.metadata import version
        return version("youtube-skillbox")
    except Exception:
        return "unknown"

# Find the skills directory from the installed package
def find_skills_dir():
    """Find the skills/youtube/scripts directory from the installed package."""
    try:
        import youtube_skillbox
        pkg_path = os.path.dirname(youtube_skillbox.__file__)
        skills_dir = os.path.join(pkg_path, "skills", "youtube", "scripts")
        if os.path.isdir(skills_dir):
            return skills_dir
    except ImportError:
        pass
    # Fallback: try relative to this file (editable install from source)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    skills_dir = os.path.join(repo_root, "skills", "youtube", "scripts")
    if os.path.isdir(skills_dir):
        return skills_dir
    raise RuntimeError("Could not locate skills/youtube/scripts directory")

def main():
    # Handle version flag early
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"ytdata {get_version()}")
        return
    
    # Check if a subcommand is provided (first arg after program name)
    # Known subcommands
    subcommands = {
        "search", "channel", "latest", "playlist", "profile", "posts",
        "sections", "shows", "home", "info", "scorecard", "outliers",
        "gap", "keywords", "compete", "trends", "track"
    }
    
    # Check if first arg after program name is a subcommand
    has_subcommand = len(sys.argv) > 1 and sys.argv[1] in subcommands
    
    # Show help only if no subcommand and help requested
    if ("--help" in sys.argv or "-h" in sys.argv) and not has_subcommand:
        parser = argparse.ArgumentParser(
            prog="ytdata",
            description="YouTube research via yt-dlp (no API key)",
        )
        parser.print_help()
        return
    
    # Pass all args to ytdata
    skills_dir = find_skills_dir()
    sys.path.insert(0, skills_dir)
    
    from ytdata import main
    main()

if __name__ == "__main__":
    main()