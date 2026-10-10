; Script Inno Setup pentru Zotai — instalare cu dezinstalare.
; Build: pyinstaller zotai.spec -> dist/Zotai/, apoi iscc installer/zotai.iss

#define MyAppName "Zotai"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Zotai"
#define MyAppExeName "Zotai.exe"

[Setup]
AppId={{8E7F4A2C-10A1-4BED-9C01-0E571A000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Zotai
DefaultGroupName=Zotai
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=ZotaiSetup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "romanian"; MessagesFile: "compiler:Languages\Romanian.isl"

[Tasks]
Name: "desktopicon"; Description: "Creează o comandă rapidă pe desktop"; GroupDescription: "Pictograme suplimentare:"
Name: "ctxmenu"; Description: "Adaugă «Procesează cu Zotai» în meniul contextual pentru PDF/DOCX"; GroupDescription: "Integrare Windows:"

[Files]
Source: "..\dist\Zotai\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Dezinstalează {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; ---- Meniul contextual Windows Explorer: «Procesează cu Zotai» pentru .pdf și .docx ----
[Registry]
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\Zotai"; \
  ValueType: string; ValueName: ""; ValueData: "Procesează cu Zotai"; \
  Flags: uninsdeletekey; Tasks: ctxmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\Zotai"; \
  ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName},0"; \
  Flags: uninsdeletevalue; Tasks: ctxmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\Zotai\command"; \
  ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; \
  Flags: uninsdeletekey; Tasks: ctxmenu

Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.docx\shell\Zotai"; \
  ValueType: string; ValueName: ""; ValueData: "Procesează cu Zotai"; \
  Flags: uninsdeletekey; Tasks: ctxmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.docx\shell\Zotai"; \
  ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName},0"; \
  Flags: uninsdeletevalue; Tasks: ctxmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.docx\shell\Zotai\command"; \
  ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; \
  Flags: uninsdeletekey; Tasks: ctxmenu

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lansează {#MyAppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Datele utilizatorului sunt păstrate implicit (zotai.db, jurnale, limbi) în %LOCALAPPDATA%\Zotai.
Type: filesandordirs; Name: "{app}"
