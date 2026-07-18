; Hermes Agent Universal - Windows NSIS Installer
; 用法: makensis hermes-installer.nsi

!define APP_NAME "Hermes Agent Universal"
!define APP_EXE "hermes-agent.exe"
!define APP_VERSION "0.1.0"
!define PUBLISHER "Hermes Agent Team"
!define URL_HOME "https://github.com/shaoyili1990/-"

; 使用 Modern UI 2
!include "MUI2.nsh"

; 基本设置
Name "${APP_NAME} ${APP_VERSION}"
OutFile "..\dist\hermes-agent-Setup-${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES64\${APP_NAME}"
RequestExecutionLevel admin

; 页面定义
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Install"
  SetOutPath "$INSTDIR"

  ; 主程序
  File "..\dist\${APP_EXE}"

  ; 资源文件
  File /r "..\fingerprints"
  File /r "..\subchains"
  File /r "..\validations"
  File "..\config.yaml"
  File "..\SKILL.md"

  ; 创建数据目录
  CreateDirectory "$INSTDIR\store"
  CreateDirectory "$LOCALAPPDATA\HermesAgent\store"

  ; 开始菜单快捷方式
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe"

  ; 桌面快捷方式
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"

  ; 卸载程序
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  RMDir /r "$INSTDIR"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\${APP_NAME}.lnk"
SectionEnd
