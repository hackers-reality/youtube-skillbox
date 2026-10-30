# Install all YouTube Skillbox skills into OpenCode's global skills directory.
$dest = Join-Path $HOME ".config\opencode\skills"
$src = Join-Path $PSScriptRoot "skills"

New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item (Join-Path $src "*") -Destination $dest -Recurse -Force

$count = (Get-ChildItem $src -Directory).Count
Write-Host "Installed $count skills -> $dest"
Write-Host "Restart your agent session to pick them up."
