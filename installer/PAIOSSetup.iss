; PAIOSSetup.iss — the PAIOS Windows installer (Inno Setup 6).
;
; Compiled by scripts/build_installer.py when ISCC.exe is installed:
;
;   ISCC /DAppVersion=<v> /DPayloadDir=<dist>\payload\app
;        /DOutputDir=<dist> /DIconFile=<repo>\assets\paios.ico
;        installer\PAIOSSetup.iss
;
; The payload directory is the standalone application tree built by
; PyInstaller (PAIOS.exe + _internal + PAIOSUpdater.exe +
; PAIOSUninstall.exe + version.txt). No Python is required on the
; user's machine.
;
; Layout contract:
;   application  ->  {app}            (Program Files\PAIOS by default)
;   user data    ->  %LOCALAPPDATA%\PAIOS   (never touched by install
;                                            or upgrade; removal only
;                                            on explicit user consent)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef PayloadDir
  #define PayloadDir "..\dist\product\payload\app"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist\product"
#endif

[Setup]
AppId={{7E2C9E5A-4B7D-4E1F-9C63-2A81D0F4B7E1}
AppName=PAIOS
AppVersion={#AppVersion}
AppVerName=PAIOS {#AppVersion}
AppPublisher=PAIOS Project
AppPublisherURL=https://github.com/adsecurto-boop/PAIOS
AppSupportURL=https://github.com/adsecurto-boop/PAIOS/issues
AppUpdatesURL=https://github.com/adsecurto-boop/PAIOS/releases
; 64-bit application: install under the real Program Files.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DefaultDirName={autopf}\PAIOS
DefaultGroupName=PAIOS
UninstallDisplayName=PAIOS
UninstallDisplayIcon={app}\PAIOS.exe
; Admin installs land in C:\Program Files\PAIOS; the user may choose a
; per-user install ({localappdata}\Programs\PAIOS) from the dialog.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline
OutputDir={#OutputDir}
OutputBaseFilename=PAIOSSetup
#ifdef IconFile
SetupIconFile={#IconFile}
#endif
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; \
    GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start PAIOS automatically at &logon"; \
    GroupDescription: "Startup:"

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PAIOS"; Filename: "{app}\PAIOS.exe"; \
    WorkingDir: "{app}"; Comment: "PAIOS - Personal AI Operating System"
Name: "{autodesktop}\PAIOS"; Filename: "{app}\PAIOS.exe"; \
    WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "PAIOS"; \
    ValueData: """{app}\PAIOS.exe"""; \
    Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\PAIOS.exe"; Description: "Launch PAIOS now"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; Ask a running PAIOS to exit before files are removed.
Filename: "{app}\PAIOS.exe"; Parameters: "--stop"; \
    Flags: runhidden skipifdoesntexist; RunOnceId: "StopPaios"

[Code]
{ The user-data question: %LOCALAPPDATA%\PAIOS holds the database,
  settings, logs and memories. Silent uninstalls always keep it. }

function UserDataDir(): String;
begin
  Result := ExpandConstant('{localappdata}\PAIOS');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Response: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DirExists(UserDataDir()) and (not UninstallSilent()) then
    begin
      Response := MsgBox(
        'Keep your PAIOS data?' + #13#10 + #13#10 +
        'YES keeps your database, settings and memories in' + #13#10 +
        UserDataDir() + #13#10 + #13#10 +
        'NO removes all PAIOS data permanently.',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON1);
      if Response = IDNO then
        DelTree(UserDataDir(), True, True, True);
    end;
  end;
end;
