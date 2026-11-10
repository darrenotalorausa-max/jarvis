# Crea el acceso directo "Jarvis OS" en el escritorio: abre Jarvis en su propia ventana, sin consola.
param([string]$Root)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $Root).Path
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop "Jarvis OS.lnk"))
$lnk.TargetPath = Join-Path $Root ".venv\Scripts\pythonw.exe"
$lnk.Arguments = "-m jarvis.launch --app"
$lnk.WorkingDirectory = Join-Path $Root "backend"
$lnk.IconLocation = (Join-Path $Root "scripts\windows\jarvis.ico") + ",0"
$lnk.Description = "Jarvis OS"
$lnk.Save()
Write-Output "Acceso directo creado en el escritorio: Jarvis OS"
