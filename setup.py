from pathlib import Path
import re

from setuptools import find_packages, setup


ROOT = Path(__file__).parent
INIT_FILE = ROOT / "youtube_skillbox" / "__init__.py"
VERSION_MATCH = re.search(
    r'^__version__ = ["\']([^"\']+)["\']',
    INIT_FILE.read_text(encoding="utf-8"),
    re.MULTILINE,
)
if VERSION_MATCH is None:
    raise RuntimeError("Could not determine package version from youtube_skillbox/__init__.py")

setup(
    name="youtube-skillbox",
    version=VERSION_MATCH.group(1),
    description=(
        "Free YouTube research toolkit — search, keywords, competition, rank "
        "tracking, SEO scorecard, outliers, content gap, trends. "
        "No user-supplied YouTube Data API key required."
    ),
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="hackers-reality",
    author_email="phulariarnav@gmail.com",
    url="https://github.com/hackers-reality/youtube-skillbox",
    packages=find_packages(exclude=["skills.yt-audit*"]),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "ytdata=youtube_skillbox.cli:main",
        ],
    },
    install_requires=["yt-dlp>=2026.10.26"],
    python_requires=">=3.11",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Multimedia :: Video",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Linguistic",
        "Typing :: Typed",
    ],
    keywords=[
        "youtube", "seo", "keyword", "research", "rank", "tracking",
        "competition", "analysis", "outliers", "trends", "scorecard",
        "content-gap", "transcript", "shorts", "metadata", "api-free",
    ],
    project_urls={
        "Source": "https://github.com/hackers-reality/youtube-skillbox",
        "Issues": "https://github.com/hackers-reality/youtube-skillbox/issues",
        "Documentation": "https://github.com/hackers-reality/youtube-skillbox#readme",
        "Changelog": "https://github.com/hackers-reality/youtube-skillbox/blob/main/CHANGELOG.md",
        "Funding": "https://github.com/sponsors/hackers-reality",
    },
)
