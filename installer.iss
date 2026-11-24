[Setup]
AppId={{F632A1FB-5209-46CB-9563-FEF4B54039D2}
AppName=CLIP SHORT Studio
AppVersion=1.0.1
AppPublisher=Firdauspeace
AppPublisherURL=https://github.com/Firdauspeace/CLIP-SHORT
AppSupportURL=https://github.com/Firdauspeace/CLIP-SHORT/issues
DefaultDirName={localappdata}\Programs\CLIP SHORT Studio
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayIcon={app}\CLIP SHORT Studio.exe
OutputDir=dist
OutputBaseFilename=CLIP-SHORT-Studio-Setup
Compression=lzma2
SolidCompression=yes
ArchiveExtraction=full
WizardStyle=modern
VersionInfoDescription=CLIP SHORT Studio Setup
VersionInfoVersion=1.0.1

[Messages]
WelcomeLabel2=Setup will install [name/ver] on your computer.%n%nKeep your internet connection on while Setup downloads the video tools.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\CLIP SHORT Studio.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.7z"; \
  DestDir: "{app}\bin"; DestName: "ffmpeg-9.0.2-essentials_build.7z"; \
  Hash: "4705843ccaaf54257c16ad90f3e952ece33c17df964ecf7bfdbb0f49c7171077"; \
  ExternalSize: 329221735; Flags: external download extractarchive recursesubdirs ignoreversion
Source: "https://github.com/denoland/deno/releases/download/v2.9.8/deno-x86_64-pc-windows-msvc.zip"; \
  DestDir: "{app}\bin"; DestName: "deno-x86_64-pc-windows-msvc.zip"; \
  Hash: "cba84b26e0df5ae7f74fc66b86a95b866872a86292ebd84fa1e959927edd93bf"; \
  ExternalSize: 98081568; Flags: external download extractarchive ignoreversion

[Icons]
Name: "{autoprograms}\CLIP SHORT Studio"; Filename: "{app}\CLIP SHORT Studio.exe"
Name: "{autodesktop}\CLIP SHORT Studio"; Filename: "{app}\CLIP SHORT Studio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CLIP SHORT Studio.exe"; Description: "Open CLIP SHORT Studio"; Flags: nowait postinstall skipifsilent
