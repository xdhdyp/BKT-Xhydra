; -- BKT-Xhydra.iss --

#pragma codePage 65001 ; 确保中文支持

; ==== 版本宏定义 ====
#define AppVersion "1.6.0"
#define AppName "Xdhdyp-BKT"
#define LauncherExePath "dist\launcher\launcher.exe"
#define StaticResPath "dist\launcher\data\static"
#define DataPath "dist\launcher\data"
#define InternalPath "dist\launcher\_internal"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName=C:\{#AppName}
DefaultGroupName={#AppName}
OutputDir=Output
OutputBaseFilename={#AppName}_Setup_{#AppVersion}_x64
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
SetupIconFile={#StaticResPath}\app_icon.ico
WizardStyle=modern
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\data\static\app_icon.ico
AppPublisher=xdhdyp
AppPublisherURL=https://github.com/xdhdyp/Xdhdyp-BKT
AppSupportURL=https://github.com/xdhdyp/Xdhdyp-BKT
AppContact=https://github.com/xdhdyp/Xdhdyp-BKT

; 中文语言支持
LanguageDetectionMethod=uilanguage
ShowLanguageDialog=no

[Languages]
Name: "cn"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
cn.DirBrowseLabel=请选择安装目录 (推荐 C:\{#AppName}):
cn.RunAfter=安装完成后启动 %1
cn.SsShortcut=创建桌面快捷方式
cn.BlockCProgram=禁止安装到C盘Program目录！
cn.AppDeveloper=开发者：闲得慌的一匹
en.AppDeveloper=Developer: XDHDYP

[Code]
function InitializeSetup(): Boolean;
var
  ErrorMessage: string;
begin
  Result := True;
end;

procedure InitializeWizard;
var
  DeveloperLabel: TLabel;
begin
  // 中文界面定制
  if ActiveLanguage = 'cn' then
  begin
    WizardForm.SelectDirLabel.Caption := '选择 {#AppName} 的安装位置';
    if WizardForm.RunList.Items.Count > 0 then
      WizardForm.RunList.Items[0] := ExpandConstant('{cm:RunAfter,{#AppName}}');
    if WizardForm.TypesCombo.Items.Count > 0 then
    begin
      WizardForm.TypesCombo.Items[0] := '标准安装';
      if WizardForm.TypesCombo.Items.Count > 1 then
        WizardForm.TypesCombo.Items[1] := '自定义安装';
    end;
    WizardForm.SelectStartMenuFolderLabel.Caption := '选择开始菜单文件夹';
  end;
  
  // 新增 - 在欢迎页面底部添加开发者信息
  DeveloperLabel := TLabel.Create(WizardForm);
  DeveloperLabel.Parent := WizardForm.WelcomePage;
  DeveloperLabel.Caption := ExpandConstant('{cm:AppDeveloper}');
  DeveloperLabel.Left := ScaleX(20);
  DeveloperLabel.Top := WizardForm.WelcomePage.Height - ScaleY(30);
  DeveloperLabel.Font.Size := 8;
  DeveloperLabel.Font.Color := clGray;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ErrorMessage: string;
  InstallDir: string;
begin
  Result := True;
  // 只在选择目录页面校验
  if CurPageID = wpSelectDir then
  begin
    InstallDir := WizardForm.DirEdit.Text;
    if (Pos('C:\\Program', InstallDir) > 0) or
       (Pos('C:\\Program Files', InstallDir) > 0) then
    begin
      if ActiveLanguage = 'cn' then
        ErrorMessage := '{cm:BlockCProgram}' + #13#10 + '请选择D盘或其他非系统目录。'
      else
        ErrorMessage := 'Installation to C:\\Program directories is blocked!' + #13#10 + 'Please select D: drive or other non-system directory.';

      MsgBox(ErrorMessage, mbError, MB_OK);
      Result := False;
    end;
  end;
end;

// 判断是否需要复制 launcher.exe
function ShouldCopyLauncher(): Boolean;
begin
  // 这里可以写你的判断逻辑，比如始终返回 True
  Result := True;
end;

// 卸载时保留 {app}\data\users 目录，其它全部删除
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  FindRec: TFindRec;
  FilePath: string;
begin
  if CurUninstallStep = usUninstall then
  begin
    // 删除 {app}\data 下除 users 文件夹外的所有内容
    if FindFirst(ExpandConstant('{app}\data\*'), FindRec) then
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') and (FindRec.Name <> 'users') then
        begin
          FilePath := ExpandConstant('{app}\data\' + FindRec.Name);
          DelTree(FilePath, True, True, True);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

[Files]
; ==== 主程序文件 ====
Source: "{#LauncherExePath}"; DestDir: "{app}"; Flags: ignoreversion

; ==== 静态资源文件 ====
; 图片资源
Source: "{#StaticResPath}\alipay_optimized.png"; DestDir: "{app}\data\static"; Flags: ignoreversion
Source: "{#StaticResPath}\login_background.png"; DestDir: "{app}\data\static"; Flags: ignoreversion
Source: "{#StaticResPath}\wechat_optimized.png"; DestDir: "{app}\data\static"; Flags: ignoreversion
Source: "{#StaticResPath}\github.png"; DestDir: "{app}\data\static"; Flags: ignoreversion

; 图标文件
Source: "{#StaticResPath}\app_icon.ico"; DestDir: "{app}\data\static"; Flags: ignoreversion

; 数据文件
Source: "{#StaticResPath}\version.txt"; DestDir: "{app}\data\static"; Flags: ignoreversion
Source: "{#StaticResPath}\单选题.xlsx"; DestDir: "{app}\data\files"; Flags: ignoreversion

; ==== 其他数据文件 ====
Source: "{#DataPath}\prompt.txt"; DestDir: "{app}\data"; Flags: ignoreversion

; ==== 配置和模型文件 ====
Source: "{#DataPath}\config"; DestDir: "{app}\data\config"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#DataPath}\models\*"; DestDir: "{app}\data\models"; Flags: recursesubdirs createallsubdirs ignoreversion

; ==== Python 运行环境 ====
Source: "{#InternalPath}\*"; DestDir: "{app}\_internal"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; 桌面快捷方式
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\launcher.exe"; IconFilename: "{app}\data\static\app_icon.ico"

; 开始菜单快捷方式
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\launcher.exe"; IconFilename: "{app}\data\static\app_icon.ico"

[Run]
; 安装完成后运行程序
Filename: "{app}\launcher.exe"; Description: "{cm:RunAfter,{#AppName}}"; Flags: nowait postinstall

[UninstallDelete]
; 卸载时删除所有文件
Type: filesandordirs; Name: "{app}"

; ==== 安装包元信息 ====