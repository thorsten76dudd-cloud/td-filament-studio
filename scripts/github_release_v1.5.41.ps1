# Run where gh is logged in: gh auth login
# Creates release v1.5.41-stable and deletes older releases.

$ErrorActionPreference = "Stop"
$Repo = "thorsten76dudd-cloud/td-filament-studio"
$Tag = "v1.5.41-stable"
$Root = Split-Path $PSScriptRoot -Parent
$Setup = Join-Path $Root "installer_output\TD-Filament-Studio-Setup.exe"
$NotesFile = Join-Path $env:TEMP "td-studio-1.5.41-notes.md"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) not found. Install from https://cli.github.com/"
}

$auth = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error ("gh not logged in. Run: gh auth login`n" + $auth)
}

if (-not (Test-Path $Setup)) {
    Write-Host "Installer missing - running build_setup.bat ..."
    Push-Location $Root
    cmd /c build_setup.bat
    Pop-Location
    if (-not (Test-Path $Setup)) {
        Write-Error ("Setup not found: " + $Setup)
    }
}

$notes = @(
    "## TD Filament Studio 1.5.41",
    "",
    "* Save and push to printer - clear feedback",
    "* Auto-sync material DB via SSH (optional)",
    "* Post-print deduct dialog remembers handled jobs",
    "* Chip duplicate / NFC (since 1.5.39)",
    "",
    "Run the Setup. Set printer IP and SSH in Material Database tab."
) -join [Environment]::NewLine
Set-Content -Path $NotesFile -Value $notes -Encoding UTF8

$OldTags = @(
    "v1.5.23-stable",
    "v1.5.24-stable",
    "v1.5.25-stable",
    "v1.5.26-stable",
    "v1.5.29-stable",
    "v1.5.38-stable",
    "v1.5.39-stable"
)

function Test-GhRelease {
    param([string]$ReleaseTag)
    $old = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    gh release view $ReleaseTag --repo $Repo 2>$null | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $old
    return $ok
}

Write-Host "=== Delete old releases ==="
foreach ($t in $OldTags) {
    if (Test-GhRelease $t) {
        Write-Host ("Deleting " + $t + " ...")
        gh release delete $t --repo $Repo --yes --cleanup-tag
    }
}

Write-Host ("=== Release " + $Tag + " ===")
if (Test-GhRelease $Tag) {
    gh release upload $Tag $Setup --repo $Repo --clobber
} else {
    gh release create $Tag $Setup --repo $Repo --title "TD Filament Studio 1.5.41" --notes-file $NotesFile --latest
}

$url = "https://github.com/" + $Repo + "/releases/tag/" + $Tag
Write-Host ""
Write-Host ("Done: " + $url)
