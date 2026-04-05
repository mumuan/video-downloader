; xhub NSIS Installer Script
; Usage: makensis xhub-installer.nsi

!include "MUI2.nsh"
!include "FileFunc.nsh"

; --- Application metadata ---
!define APPNAME "xhub"
!define COMPANYNAME "xhub"
!define DESCRIPTION "xhub - 视频下载器"
!define VERSIONMAJOR 1
!define VERSIONMINOR 0
!define VERSIONBUILD 0
!define INSTALLSIZE 350000

; --- Installer attributes ---
Name "${APPNAME}"
OutFile "xhub-installer.exe"
InstallDir "$PROGRAMFILES\${APPNAME}"
InstallDirRegKey HKLM "Software\${COMPANYNAME}\${APPNAME}" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

; --- Modern UI settings ---
!define MUI_ICON "assets\icon.ico"
!define MUI_UNICON "assets\icon.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEFINISHPAGE_BITMAP_NOSTRETCH

; --- Pages ---
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

; --- Installation section ---
Section "Install"
    SetOutPath $INSTDIR

    ; Install main executable
    File "dist\xhub.exe"

    ; Install bundled Playwright browsers (if present in dist)
    IfFileExists "dist\ms-playwright\*.*" 0 +2
        SetOutPath "$INSTDIR\ms-playwright"
        File /r "dist\ms-playwright\*.*"

    ; Restore $INSTDIR after recursive File
    SetOutPath $INSTDIR

    ; Store install path in registry (R7)
    WriteRegStr HKLM "Software\${COMPANYNAME}\${APPNAME}" "InstallDir" "$INSTDIR"

    ; Create uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; Write uninstall registry entries (R8)
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayIcon" "$\"$INSTDIR\xhub.exe$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${COMPANYNAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "VersionMajor" ${VERSIONMAJOR}
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "VersionMinor" ${VERSIONMINOR}
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoRepair" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "EstimatedSize" ${INSTALLSIZE}

    ; Create Start Menu shortcuts (R6)
    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\xhub.exe" "" "$INSTDIR\xhub.exe" 0
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME} (卸载).lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0

    ; Create Desktop shortcut (R6)
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\xhub.exe" "" "$INSTDIR\xhub.exe" 0
SectionEnd

; --- Uninstallation section ---
Section "Uninstall"
    ; Remove installed files
    Delete "$INSTDIR\xhub.exe"
    Delete "$INSTDIR\uninstall.exe"

    ; Remove bundled browsers
    RMDir /r "$INSTDIR\ms-playwright"

    ; Remove install directory
    RMDir "$INSTDIR"

    ; Remove Start Menu shortcuts
    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME} (卸载).lnk"
    RMDir "$SMPROGRAMS\${APPNAME}"

    ; Remove Desktop shortcut
    Delete "$DESKTOP\${APPNAME}.lnk"

    ; Remove registry entries
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
    DeleteRegKey HKLM "Software\${COMPANYNAME}\${APPNAME}"
SectionEnd
