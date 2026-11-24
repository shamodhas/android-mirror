[Setup]
AppId={{8E4A9B21-4F3C-4C9A-9D12-7A1B5E3C2026}
AppName=Air Screen
AppVersion=3.0.0
AppPublisher=Shamodha Sahan
AppPublisherURL=https://github.com/shamodhas/android-wifi-mirror-scrcpy-pc
DefaultDirName={autopf}\Air Screen
DefaultGroupName=Air Screen
OutputDir=Output
OutputBaseFilename=AirScreen-Setup-v3.0.0
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\AirScreen.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ChangesEnvironment=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce
Name: "addtopath"; Description: "Add bundled ADB & scrcpy tools to user PATH"; GroupDescription: "Environment setup:"; Flags: checkedonce

[Files]
Source: "dist\AirScreen.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "%LOCALAPPDATA%\android-wifi-mirror-scrcpy-pc\tools\*"; DestDir: "{app}\tools"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\Air Screen"; Filename: "{app}\AirScreen.exe"
Name: "{group}\Uninstall Air Screen"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Air Screen"; Filename: "{app}\AirScreen.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}\tools"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}\tools'))

[Run]
Filename: "{app}\AirScreen.exe"; Description: "Launch Air Screen"; Flags: nowait postinstall skipifsilent

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Uppercase(Param) + ';', ';' + Uppercase(OrigPath) + ';') = 0;
end;