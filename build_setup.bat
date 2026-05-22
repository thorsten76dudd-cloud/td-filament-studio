@echo off
setlocal
cd /d "%~dp0"

echo === TD Filament Studio — Setup-Build ===
echo.

tasklist /FI "IMAGENAME eq TD Filament Studio.exe" 2>nul | find /I "TD Filament Studio.exe" >nul
if %ERRORLEVEL%==0 (
    echo App laeuft noch — wird beendet...
    taskkill /IM "TD Filament Studio.exe" /F >nul 2>&1
    timeout /t 2 /nobreak >nul
)

python -m pip install -q -r requirements.txt pyinstaller
if errorlevel 1 (
    echo pip fehlgeschlagen.
    exit /b 1
)

echo [1/2] PyInstaller ...
python -m PyInstaller --noconfirm "TD Filament Studio.spec"
if errorlevel 1 (
    echo PyInstaller fehlgeschlagen.
    exit /b 1
)

if not exist "dist\TD Filament Studio\TD Filament Studio.exe" (
    echo EXE nicht gefunden: dist\TD Filament Studio\TD Filament Studio.exe
    exit /b 1
)

echo.
echo EXE: dist\TD Filament Studio\TD Filament Studio.exe
for %%A in ("dist\TD Filament Studio\TD Filament Studio.exe") do echo Groesse: %%~zA Bytes
echo.

set ISCC=
where iscc >nul 2>&1 && set ISCC=iscc
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not "%ISCC%"=="" (
    echo [2/2] Inno Setup Installer ...
    python scripts\sync_installer_version.py
    if errorlevel 1 (
        echo Versions-Sync fehlgeschlagen.
        exit /b 1
    )
    "%ISCC%" "installer\setup.iss"
    if errorlevel 1 (
        echo Inno Setup fehlgeschlagen.
        exit /b 1
    )
    echo.
    echo === Fertig ===
    echo Setup:  installer_output\TD-Filament-Studio-Setup.exe
    echo Portable: dist\TD Filament Studio\TD Filament Studio.exe
) else (
    echo [2/2] Inno Setup nicht gefunden — nur portable EXE.
    echo.
    echo Optional: Inno Setup 6 installieren, dann build_setup.bat erneut starten.
    echo   https://jrsoftware.org/isdl.php
    echo.
    echo === Fertig (nur EXE) ===
    echo dist\TD Filament Studio\TD Filament Studio.exe
)

echo.
pause
