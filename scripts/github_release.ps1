# Usage: gh auth login  (once)
# Creates new stable release. Previous releases stay on GitHub.
# Use -RemoveTag <tag> to delete a single old release explicitly,
# or -DeleteAllOldReleases to wipe everything except the current $Tag.

param(
    [string]$Version = "1.5.142",
    [string]$Tag = "v1.5.142-stable",
    [string]$Repo = "thorsten76dudd-cloud/td-filament-studio",
    [string]$RemoveTag = "",
    [switch]$DeleteAllOldReleases
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
    "### Material-DB",
    "* Mehr Creality-Profile nach „Vom Drucker (SSH)“ (erweiterte JSON-Felder).",
    "* Hinweis: Creality-Print-Sync reicht nicht - SSH-Laden noetig; Warnung bei unveraenderter Eintragszahl.",
    "",
    "Details: STABLE-v$Version.md im Repository."
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

if ($DeleteAllOldReleases) {
    $releases = gh release list --repo $Repo --limit 100 --json tagName -q ".[].tagName" 2>$null
    if ($releases) {
        foreach ($t in $releases) {
            if ($t -eq $Tag) { continue }
            Write-Host ("Removing old release " + $t + " ...")
            gh release delete $t --repo $Repo --yes --cleanup-tag 2>$null
        }
    }
} elseif ($RemoveTag -and (Test-GhRelease $RemoveTag)) {
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
