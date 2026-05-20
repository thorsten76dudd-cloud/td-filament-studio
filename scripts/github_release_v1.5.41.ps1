# Ausfuehren in PowerShell/CMD, wo gh eingeloggt ist:  gh auth login
# Erstellt Release v1.5.41-stable und loescht alle aelteren Releases.

$ErrorActionPreference = "Stop"
$Repo = "thorsten76dudd-cloud/td-filament-studio"
$Tag = "v1.5.41-stable"
$Root = Split-Path $PSScriptRoot -Parent
$Setup = Join-Path $Root "installer_output\TD-Filament-Studio-Setup.exe"
$NotesFile = Join-Path $env:TEMP "td-studio-1.5.41-notes.md"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) nicht gefunden. https://cli.github.com/"
}

$auth = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "gh nicht eingeloggt. Bitte ausfuehren: gh auth login`n$auth"
}

if (-not (Test-Path $Setup)) {
    Write-Host "Installer fehlt — baue build_setup.bat ..."
    Push-Location $Root
    cmd /c build_setup.bat
    Pop-Location
    if (-not (Test-Path $Setup)) { Write-Error "Setup nicht gefunden: $Setup" }
}

$notes = @(
    "## TD Filament Studio 1.5.41",
    "",
    "* Speichern und an Drucker - klares Feedback",
    "* Auto-Sync Material-DB per SSH (optional)",
    "* Verbrauchs-Dialog merkt erledigte Drucke",
    "* Chip-Duplikat / NFC (ab 1.5.39)",
    "",
    "Setup ausfuehren. Drucker-IP und SSH im Tab Material-Datenbank."
) -join "`n"
Set-Content -Path $NotesFile -Value $notes -Encoding UTF8

$OldTags = @(
    "v1.5.23-stable", "v1.5.24-stable", "v1.5.25-stable", "v1.5.26-stable",
    "v1.5.29-stable", "v1.5.38-stable", "v1.5.39-stable"
)

Write-Host "=== Alte Releases loeschen ==="
foreach ($t in $OldTags) {
    gh release view $t --repo $Repo 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Loesche $t ..."
        gh release delete $t --repo $Repo --yes --cleanup-tag
    }
}

Write-Host "=== Release $Tag ==="
gh release view $Tag --repo $Repo 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    gh release upload $Tag $Setup --repo $Repo --clobber
} else {
    gh release create $Tag $Setup --repo $Repo --title "TD Filament Studio 1.5.41" --notes-file $NotesFile --latest
}

Write-Host ""
Write-Host "Fertig: https://github.com/$Repo/releases/tag/$Tag"
