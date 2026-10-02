; Instalador de Shinobi.pdf (Inno Setup 6)
; Se compila con:  python tools/build_installer.py   (primero hay que generar dist\Shinobi con build_exe.py)
;
; - Se instala solo para el usuario actual: no pide permisos de administrador (sin cartel de UAC).
; - El asistente pregunta el idioma y lo guarda en HKCU\Software\ShinobiPDF\Language; la app lo lee
;   la primera vez que se abre (después se puede cambiar desde Ajustes).

#define AppName "Shinobi.pdf"
#define AppId "ShinobiPDF"
#define ExeName "Shinobi.exe"
#ifndef AppVersion
  #define AppVersion "1.1"
#endif
#ifndef AppPublisher
  #define AppPublisher "Shinobi.pdf"
#endif
#ifndef AppUrl
  #define AppUrl "https://github.com/"
#endif

[Setup]
; El AppId identifica la app para actualizaciones y desinstalación: no cambiarlo nunca
AppId={{6A1F3C2E-8D4B-4E9A-B7C5-2F0D9E3A1B48}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppId}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=ShinobiPDF-Setup
SetupIconFile=..\shinobi\assets\icon.ico
UninstallDisplayIcon={app}\{#ExeName}
UninstallDisplayName={#AppName}
WizardStyle=modern
; Página de bienvenida con el panel lateral de la marca (Inno Setup la omite por defecto)
DisableWelcomePage=no
WizardImageFile=installer_large.bmp
WizardSmallImageFile=installer_small.bmp
ShowLanguageDialog=yes
UsePreviousLanguage=no
CloseApplications=yes
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
english.ContextMenuVerb=Split with Shinobi.pdf
spanish.ContextMenuVerb=Dividir con Shinobi.pdf
english.IntegrationGroup=Windows integration:
spanish.IntegrationGroup=Integración con Windows:
english.ContextMenuTask=Add "Split with Shinobi.pdf" to the right-click menu of PDF files
spanish.ContextMenuTask=Agregar "Dividir con Shinobi.pdf" al menú del clic derecho de los PDF

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "contextmenu"; Description: "{cm:ContextMenuTask}"; GroupDescription: "{cm:IntegrationGroup}"

[Files]
Source: "..\dist\Shinobi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Registry]
; Idioma elegido en el asistente ("english" / "spanish")
Root: HKCU; Subkey: "Software\{#AppId}"; ValueType: string; ValueName: "Language"; ValueData: "{language}"; Flags: uninsdeletekey
; Menú contextual de los PDF (la misma clave que activa/desactiva Ajustes en la app)
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\{#AppId}"; ValueType: string; ValueName: ""; ValueData: "{cm:ContextMenuVerb}"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\{#AppId}"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#ExeName}"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\{#AppId}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#ExeName}"" ""%1"""; Tasks: contextmenu
; Al desinstalar se borra el menú contextual aunque se haya activado desde la app
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\{#AppId}"; Flags: uninsdeletekey dontcreatekey

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
