@echo off
setlocal
cd /d "%~dp0\.."

set "EXE=%CD%\dist\TD Filament Studio.exe"
if not exist "%EXE%" set "EXE=%LOCALAPPDATA%\Programs\TD Filament Studio\TD Filament Studio.exe"
if not exist "%EXE%" set "EXE=%ProgramFiles%\TD Filament Studio\TD Filament Studio.exe"
set "ICO=%LOCALAPPDATA%\Programs\TD Filament Studio\app_icon.ico"
if not exist "%ICO%" set "ICO=%CD%\assets\icons\app_icon.ico"
if not exist "%EXE%" (
    echo EXE nicht gefunden. Zuerst installieren oder build_exe.bat ausfuehren.
    pause
    exit /b 1
)

set "DESK=%USERPROFILE%\Desktop"
set "LNK=%DESK%\TD Filament Studio.lnk"

powershell -NoProfile -Command ^
  "$s = New-Object -ComObject WScript.Shell; $l = $s.CreateShortcut('%LNK%'); $l.TargetPath = '%EXE%'; $l.WorkingDirectory = Split-Path '%EXE%'; $l.IconLocation = '%ICO%,0'; $l.Save()"

echo Verknuepfung erstellt: %LNK%
echo Ziel: %EXE%
pause
