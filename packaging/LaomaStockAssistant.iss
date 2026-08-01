#ifndef MyAppName
  #define MyAppName "老马智能股票盯盘助手"
#endif
#ifndef MyAppVersion
  #define MyAppVersion "1.6.2"
#endif
#ifndef MyAppPublisher
  #define MyAppPublisher "老马内部研究"
#endif
#ifndef MyAppExeName
  #define MyAppExeName "LaomaStockAssistant.exe"
#endif
#ifndef SourceReleaseName
  #define SourceReleaseName "LaomaStockAssistant-Exe-" + MyAppVersion
#endif

[Setup]
AppId={{A1D44777-4D2A-4A75-933A-0D9147E5A161}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\LaomaStockAssistant
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\formal
OutputBaseFilename=LaomaStockAssistant-Setup-{#MyAppVersion}
SetupIconFile=..\assets\laoma-stock.ico
LicenseFile=LICENSE.txt
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
AppMutex=LaomaStockAssistant.Singleton
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} 安装程序
VersionInfoProductName={#MyAppName}

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: checkedonce

[Files]
Source: "..\dist\{#SourceReleaseName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
