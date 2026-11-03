#!/usr/bin/env python3
"""
YouTube Skillbox - CLI entry point.
"""
import os
import sys
import sysconfig


def get_version():
    """Return the installed distribution version when available."""
    try:
        from importlib.metadata import version
        return version("youtube-skillbox")
    except Exception:
        return "unknown"


def _installed_engine_candidates():
    """Find the engine using the wheel's own RECORD metadata first.

    Wheel data-files are relocated by installers (especially with --user and
    virtual environments). Distribution.locate_file() applies that relocation,
    avoiding assumptions about sys.prefix or platform-specific install paths.
    """
    try:
        from importlib.metadata import distribution

        dist = distribution("youtube-skillbox")
        for entry in dist.files or ():
            normalized = str(entry).replace("\\", "/")
            if normalized.endswith(
                "share/youtube-skillbox/skills/youtube/scripts/ytdata.py"
            ):
                yield str(dist.locate_file(entry).parent)
    except (ImportError, OSError, ValueError):
        pass

    # Compatibility fallback for older metadata implementations / installs.
    prefixes = []
    data_prefix = sysconfig.get_path("data")
    if data_prefix:
        prefixes.append(data_prefix)

    try:
        user_scheme = sysconfig.get_preferred_scheme("user")
        user_data_prefix = sysconfig.get_path("data", scheme=user_scheme)
    except (AttributeError, KeyError, ValueError):
        user_data_prefix = None

    if user_data_prefix and user_data_prefix not in prefixes:
        prefixes.append(user_data_prefix)

    for prefix in prefixes:
        yield os.path.join(
            prefix, "share", "youtube-skillbox", "skills", "youtube", "scripts"
        )


def find_skills_dir():
    """Locate ytdata.py in an installed wheel or a source checkout."""
    candidates = list(_installed_engine_candidates())

    # Editable installs and source checkouts keep skills/ at the repository root.
    package_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(package_dir)
    candidates.append(os.path.join(repo_root, "skills", "youtube", "scripts"))

    for skills_dir in candidates:
        if os.path.isfile(os.path.join(skills_dir, "ytdata.py")):
            return skills_dir

    searched = "\n  - ".join(candidates)
    raise RuntimeError(
        "Could not locate the bundled ytdata.py engine. Searched:\n  - "
        + searched
        + "\nReinstall youtube-skillbox or run from a complete source checkout."
    )


def main():
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"ytdata {get_version()}")
        return

    skills_dir = find_skills_dir()
    sys.path.insert(0, skills_dir)

    from ytdata import main as ytdata_main
    ytdata_main()


if __name__ == "__main__":
    main()
