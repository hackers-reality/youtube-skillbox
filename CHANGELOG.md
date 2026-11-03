# Changelog

## [0.4.5] - 2026-11-04

### Fixed
- **Installed CLI runtime lookup**: Resolve the bundled `ytdata.py` through the installed wheel's RECORD metadata so relocated data-files are found reliably across virtual environments and user installs; retain sysconfig and source-checkout fallbacks.
- **Skill installers**: Both shell and PowerShell installers now verify that the shared engine was copied to `youtube/scripts/ytdata.py` and report its installed location.

### Tests
- Added regression coverage for wheel metadata relocation and source-checkout fallback.
- The release workflow must exercise the installed CLI's real `--help` path, not only its version string.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.4] - 2026-11-04

### Added
- **`--full-meta` flag** for `search`, `channel`, `latest` commands to enrich results with full metadata via yt-dlp
  - Populates: `upload_date`, `live_status`, `channel_url`, `verified`, `age_days`, `tags`, `likes`, `subscribers`, `categories`
  - Fixes null fields in search/channel/latest outputs

### Fixed
- **Metadata completeness**: All fields now populated when using `--full-meta` (previously null: channel_url, verified, age_days)
- **PyPI publishing**: Fixed OIDC trusted publishing workflow with `id-token: write` permission
- **Workflow YAML**: Fixed encoding issues (em dash) and removed empty `with:` key

### Changed
- **Release process**: PyPI publishing now uses GitHub Actions OIDC trusted publishing (no API token needed)

## [0.4.3] - 2026-11-03

### Fixed
- **CLI**: Delegated ALL args to `ytdata.main()` for proper subcommand/help handling
  - `ytdata --version` / `ytdata -v` shows version
  - `ytdata --help` / `ytdata -h` shows **all 17 subcommands** (search, channel, latest, playlist, profile, posts, sections, shows, home, info, scorecard, outliers, gap, keywords, compete, trends, track)
  - Subcommand help (e.g., `ytdata search --help`) passes through to ytdata

### Removed
- **Deprecated skill**: `yt-audit` excluded from package distribution (use `yt-workflow` instead)

### Fixed
- **Packaging**: Exclude `yt-audit` skill from wheel via `packages.find.exclude` and `MANIFEST.in prune`
- **Search results**: `info` command returns full metadata (upload_date, live_status, tags, etc.) via yt-dlp; search uses Innertube for locale-pinned results

## [0.4.2] - 2026-11-03

### Fixed
- **CLI entry point**: Fixed `ytdata` console script entry point in `pyproject.toml` (was missing `[project.scripts]` section)
- **CLI entry point**: Fixed `ytdata` console script to be properly registered in wheel metadata

### Changed
- **Packaging**: Fixed `pyproject.toml` to use `[project.scripts]` instead of `setup.py` entry_points for modern packaging

### Fixed
- **CLI entry point**: `ytdata` console script now properly registered in wheel metadata

### Documentation
- **PyPI page**: Package metadata now renders correctly on PyPI with proper CLI entry point

## [0.4.1] - 2026-11-03

### Fixed
- **CLI**: Added `--version` / `-v` and `--help` / `-h` support with subcommand detection
  - `ytdata --version` / `ytdata -v` shows version
  - `ytdata --help` / `ytdata -h` shows top-level help (only when no subcommand)
  - Subcommand help (e.g., `ytdata search --help`) passes through to ytdata
- **Packaging**: Fixed wheel to include all skill packages with proper `__init__.py` files
- **CLI entry point**: Fixed `ytdata` command to work from installed wheel (finds skills dir from installed package)
- **Documentation**: Added disclaimer to README, updated `yt-workflow/SKILL.md` with installed `ytdata` CLI usage
- **Deprecated skill**: `yt-audit` marked DEPRECATED, redirects to `yt-workflow`

### Changed
- **Scoring weights fixed**: Competition scoring now totals 100% (35+25+20+15+5=100)
- **Retention CSV parsing**: Fixed percentage position handling with `--duration` flag
- **Title scoring**: Keyword-dependent rules excluded from weight when no keyword provided
- **Competition title matching**: Token-level matching instead of substring matching
- **Packaging**: Fixed wheel to include all skill packages with proper `__init__.py` files

### Added
- **THIRD_PARTY_LICENSES/**: Added upstream MIT license for `youtube-agent-skill` (Jake Schincariol)
- **MANIFEST.in**: Explicit manifest to include skills, tests, and licenses
- **Regression test suite**: 84 tests covering all 17 CLI subcommands, retention, title scoring, viral analysis

### Documentation
- **README.md**: Added disclaimer, corrected skill counts (10 creator skills, 13 active skills)
- **yt-workflow/SKILL.md**: Updated with installed `ytdata` CLI usage, corrected paths
- **yt-audit/SKILL.md**: Marked DEPRECATED with migration guide to `yt-workflow`
- **yt-viral/SKILL.md**: Added performance note pointing to faster `ytdata outliers`
- **README.md**: Corrected skill counts (13 active skills, 10 creator skills, 17 CLI subcommands)

## [0.4.0] - 2026-11-02

### Added
- 17 CLI subcommands in `ytdata`: search, keywords, compete, trends, track, scorecard, outliers, gap, profile, sections, channel, latest, posts, home, shows, playlist, info
- 10 creator skills: yt-script, yt-package, yt-seo, yt-chapters, yt-shorts, yt-edit, yt-retention, yt-viral, yt-plan, yt-comment
- 2 data skills: youtube (research), transcript
- 1 workflow skill: yt-workflow (7-phase pipeline)
- THIRD_PARTY_LICENSES with upstream MIT license attribution
- GitHub Actions workflow for PyPI publishing via OIDC trusted publishing

### Fixed
- Scoring weights: 35+25+20+15+5=100% (was 105%)
- Retention CSV parsing for YouTube Studio percentage format
- Video ID extraction supports youtu.be URLs
- Sections command distinguishes missing tabs from network errors

### Documentation
- README.md: Updated skill counts, corrected API key wording
- yt-workflow/SKILL.md: Correct paths, yt-package usage, yt-workflow phases
- yt-audit/SKILL.md: Marked DEPRECATED with migration guide

## [0.3.0] - 2026-10-30

### Added
- Initial public release
- 17 ytdata CLI subcommands
- 13 skills (10 creator + 2 data + 1 workflow)
- yt-workflow 7-phase pipeline
- GitHub Actions CI/CD with PyPI trusted publishing

## [0.2.0] - 2026-10-25

### Added
- ytdata CLI with 10 subcommands
- Core skills: yt-script, yt-package, yt-seo, yt-retention, yt-viral

## [0.1.0] - 2026-10-20

### Added
- Initial private release
- Basic ytdata CLI with search, channel, profile commands