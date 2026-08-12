#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#define AppName "Harvis"
#define AppPublisher "Uryastra"
#define AppURL "https://github.com/uryastra-beep/Harvis"
#define AppExeName "Harvis.exe"

[Setup]
AppId={{6C6A0D86-E13D-4722-8C20-928F808AD1F6}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\Harvis
DefaultGroupName=Harvis
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=Harvis-Setup-{#AppVersion}-Windows-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startup"; Description: "Start Harvis when I sign in"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\Harvis\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Harvis"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall Harvis"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Harvis"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\Harvis"; Filename: "{app}\{#AppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Harvis"; Flags: nowait postinstall skipifsilent
