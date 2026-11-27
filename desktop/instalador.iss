#define MyAppName "SISMOC El Cumbe"
#define MyAppVersion "1.0.0"
[Setup]
AppId={{92072308-C216-47DA-81A8-51BC9470F86E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Transportes El Cumbe
DefaultDirName={localappdata}\Programs\SISMOC-ElCumbe
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=instaladores
OutputBaseFilename=SISMOC-Escritorio-Instalador
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\SISMOC.exe
CloseApplications=yes
[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
[Files]
Source: "dist\SISMOC\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\SISMOC El Cumbe"; Filename: "{app}\SISMOC.exe"
Name: "{userdesktop}\SISMOC El Cumbe"; Filename: "{app}\SISMOC.exe"
[Run]
Filename: "{app}\SISMOC.exe"; Description: "Abrir SISMOC El Cumbe"; Flags: nowait postinstall skipifsilent
; Los datos están fuera de {app}. Actualizar o desinstalar no los elimina.
