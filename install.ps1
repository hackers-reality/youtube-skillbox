# Install active YouTube Skillbox skills into an agent's skills directory.
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Dest
)

$src = Join-Path $PSScriptRoot "skills"

New-Item -ItemType Directory -Path $Dest -Force | Out-Null

$activeSkills = Get-ChildItem $src -Directory | Where-Object { $_.Name -ne "yt-audit" }
foreach ($skill in $activeSkills) {
    Copy-Item $skill.FullName -Destination $Dest -Recurse -Force
}

Write-Host "Installed $($activeSkills.Count) active skills -> $Dest"
Write-Host "Restart your agent session to pick them up."