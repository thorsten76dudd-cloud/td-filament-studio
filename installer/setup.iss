; Inno Setup — TD Filament Studio
; Kompilieren: iscc installer\setup.iss  (Inno Setup 6)

#define MyAppName "TD Filament Studio"
#define MyAppVersion "1.5.136"
#define MyAppPublisher "TD"
#define MyAppExeName "TD Filament Studio.exe"

[Setup]
AppId={{A8F3C2E1-9B4D-4F2A-8E1C-TDFilamentStudio}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
OutputDir=..\installer_output
OutputBaseFilename=TD-Filament-Studio-Setup
SetupIconFile=..\assets\icons\app_icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
; EXE freigeben: Haupt-App + Hintergrund-Waechter (--watch-creality)
CloseApplications=force
CloseApplicationsFilter={#MyAppExeName}

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem Desktop"; GroupDescription: "Zusätzlich:"; Flags: unchecked

[Files]
Source: "..\dist\TD Filament Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\icons\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
; Keine leeren Nutzerdaten überschreiben (Spulen/Historie bleiben beim Update erhalten)
Source: "..\data\*"; DestDir: "{app}\data"; Flags: ignoreversion onlyifdoesntexist recursesubdirs createallsubdirs; Excludes: "spools.json,print_history.json"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
; Standard: nicht automatisch starten (Haken nur bei bewusster Auswahl)
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} starten"; Flags: nowait postinstall skipifsilent unchecked

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  I: Integer;
begin
  { Waechter und Haupt-App beenden, sonst DeleteFile Code 5 }
  { Ohne /T: sonst werden Installer-Helfer (wscript) der App mit beendet }
  for I := 1 to 4 do
  begin
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM "{#MyAppExeName}" /F', '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode);
    Sleep(700);
  end;
  Result := '';
end;
