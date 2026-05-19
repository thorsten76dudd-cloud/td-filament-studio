@echo off

setlocal

REM TD Filament Studio — portable .exe



cd /d "%~dp0"



echo Pruefe laufende Instanz...

tasklist /FI "IMAGENAME eq TD Filament Studio.exe" 2>nul | find /I "TD Filament Studio.exe" >nul

if %ERRORLEVEL%==0 (

    echo.

    echo TD Filament Studio laeuft noch — wird beendet, damit die EXE neu gebaut werden kann.

    taskkill /IM "TD Filament Studio.exe" /F >nul 2>&1

    timeout /t 2 /nobreak >nul

)



python -m pip install -q -r requirements.txt pyinstaller

if errorlevel 1 (

    echo pip install fehlgeschlagen.

    pause

    exit /b 1

)



echo.

echo Baue EXE...

python -m PyInstaller --noconfirm --clean "TD Filament Studio.spec"

if errorlevel 1 (

    echo.

    echo BUILD FEHLGESCHLAGEN — siehe Meldungen oben.

    echo Tipp: App schliessen, Antivirus kurz pruefen, erneut starten.

    pause

    exit /b 1

)



echo.

echo Fertig: dist\TD Filament Studio.exe

for %%F in ("dist\TD Filament Studio.exe") do echo Groesse: %%~zF Bytes  —  %%~tF

pause


