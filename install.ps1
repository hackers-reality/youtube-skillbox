# Install all YouTube Skillbox skills into an agent's skills directory.
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Dest
)

$src = Join-Path $PSScriptRoot "skills"

New-Item -ItemType Directory -Path $Dest -Force | Out-Null
Copy-Item (Join-Path $src "*") -Destination $Dest -Recurse -Force

$count = (Get-ChildItem $src -Directory).Count
Write-Host "Installed $count skills -> $Dest"
Write-Host "Restart your agent session to pick them up."
