@echo off
setlocal
cd /d "%~dp0"

echo Pruefe dist\TD Filament Studio.exe ...
if not exist "dist\TD Filament Studio\TD Filament Studio.exe" (
    echo.
    echo EXE fehlt — zuerst build_exe.bat ausfuehren.
    pause
    exit /b 1
)

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo Inno Setup 6 nicht gefunden. Installieren: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

echo.
echo Baue Setup-Installer...
"%ISCC%" "installer\setup.iss"
if errorlevel 1 (
    echo BUILD FEHLGESCHLAGEN.
    pause
    exit /b 1
)

echo.
echo Fertig: installer_output\TD-Filament-Studio-Setup.exe
for %%F in ("installer_output\TD-Filament-Studio-Setup.exe") do echo Groesse: %%~zF Bytes  —  %%~tF
pause
