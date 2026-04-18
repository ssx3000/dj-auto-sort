; Inno Setup script for DJ Auto-Sort.
;
; Compile via the build helper (recommended):
;     python packaging/build.py --installer
;
; Or directly with Inno Setup's compiler:
;     ISCC.exe packaging\installer.iss
;     ISCC.exe /DAppVersion=0.2.0 packaging\installer.iss
;
; Output goes to dist\dj-auto-sort-setup-<version>.exe.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName "DJ Auto-Sort"
#define AppPublisher "NovaGrid"
#define AppExeName "dj-auto-sort.exe"
#define AppURL "https://novagridhosting.com"

[Setup]
; NEVER change AppId across versions — upgrades key off this GUID.
AppId={{8F3A4E21-6D5C-4B9A-A1E7-2F8D0C6B4A93}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
OutputDir=..\dist
OutputBaseFilename=dj-auto-sort-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
