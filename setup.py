from setuptools import setup, find_packages

setup(
    name="youtube-skillbox",
    version="0.3.0",
    description="Free YouTube research toolkit — search, keywords, competition, rank tracking, SEO scorecard, outliers, content gap, trends. No API key, $0 forever.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="hackers-reality",
    author_email="phulariarnav@gmail.com",
    url="https://github.com/hackers-reality/youtube-skillbox",
    packages=find_packages(where="skills"),
    package_dir={"": "skills"},
    py_modules=["youtube.scripts.ytdata"],
    entry_points={
        "console_scripts": [
            "ytdata=youtube.scripts.ytdata:main",
        ],
    },
    install_requires=[
        "yt-dlp>=2026.10.26",
    ],
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Multimedia :: Video",
    ],
    keywords="youtube seo keyword research rank tracking competition analysis",
    project_urls={
        "Source": "https://github.com/hackers-reality/youtube-skillbox",
        "Issues": "https://github.com/hackers-reality/youtube-skillbox/issues",
    },
)