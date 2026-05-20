# Usage: gh auth login  (once)
# Creates latest stable release and removes the previous stable release tag.

param(
    [string]$Version = "1.5.44",
    [string]$Tag = "v1.5.44-stable",
    [string]$Repo = "thorsten76dudd-cloud/td-filament-studio",
    [string]$RemoveTag = "v1.5.43-stable"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Setup = Join-Path $Root "installer_output\TD-Filament-Studio-Setup.exe"
$NotesFile = Join-Path $env:TEMP "td-studio-release-notes.md"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) not found."
}
gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "Run: gh auth login" }

if (-not (Test-Path $Setup)) {
    Write-Host "Building installer ..."
    Push-Location $Root
    cmd /c build_setup.bat
    Pop-Location
    if (-not (Test-Path $Setup)) { Write-Error "Setup missing: $Setup" }
}

$notes = @(
    "## TD Filament Studio $Version",
    "",
    "* After DB upload: manual printer restart hint (power off/on)",
    "* No automatic SSH reboot (more reliable for CFS)",
    "* Save and push to printer, post-print deduct memory",
    "",
    "Run Setup. Set printer IP and SSH in Material Database tab."
) -join [Environment]::NewLine
Set-Content -Path $NotesFile -Value $notes -Encoding UTF8

function Test-GhRelease([string]$ReleaseTag) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    gh release view $ReleaseTag --repo $Repo 2>$null | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $old
    return $ok
}

if ($RemoveTag -and (Test-GhRelease $RemoveTag)) {
    Write-Host ("Removing old release " + $RemoveTag + " ...")
    gh release delete $RemoveTag --repo $Repo --yes --cleanup-tag
}

Write-Host ("=== Release " + $Tag + " ===")
if (Test-GhRelease $Tag) {
    gh release upload $Tag $Setup --repo $Repo --clobber
} else {
    gh release create $Tag $Setup --repo $Repo --title ("TD Filament Studio " + $Version) --notes-file $NotesFile --latest
}

$url = "https://github.com/" + $Repo + "/releases/tag/" + $Tag
Write-Host ("Done: " + $url)
