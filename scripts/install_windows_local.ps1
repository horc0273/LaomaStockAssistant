param(
  [switch]$IncludeCurrentData,
  [int]$Port = 8788
)

$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent $PSScriptRoot
$InstallRoot = Join-Path $env:LOCALAPPDATA "LaomaStockAssistant\app"
$DataRoot = Join-Path $env:APPDATA "LaomaStockAssistant"
$Desktop = [Environment]::GetFolderPath("Desktop")
$LauncherPath = Join-Path $InstallRoot "scripts\run_windows.ps1"

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null

$excludeDirs = @("__pycache__", ".venv", "dist")
$excludeFiles = @("server.out.log", "server.err.log")

Get-ChildItem -LiteralPath $SourceRoot -Force | ForEach-Object {
  if ($excludeDirs -contains $_.Name) { return }
  if ($excludeFiles -contains $_.Name) { return }
  if ($_.Name -eq "data") { return }
  $dest = Join-Path $InstallRoot $_.Name
  if ($_.PSIsContainer) {
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force
  } else {
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
  }
}

if ($IncludeCurrentData -and (Test-Path (Join-Path $SourceRoot "data"))) {
  Copy-Item -Path (Join-Path $SourceRoot "data\*") -Destination $DataRoot -Recurse -Force
}

$Target = "powershell.exe"
$Arguments = "-ExecutionPolicy Bypass -NoProfile -File `"$LauncherPath`" -Port $Port"
$Shell = New-Object -ComObject WScript.Shell
$ShortcutNames = @(
  "Laoma Stock Assistant.lnk",
  ((-join ([char[]](0x8001,0x9A6C,0x667A,0x80FD,0x80A1,0x7968,0x76EF,0x76D8,0x52A9,0x624B))) + ".lnk")
)
foreach ($ShortcutName in $ShortcutNames) {
  $ShortcutPath = Join-Path $Desktop $ShortcutName
  $Shortcut = $Shell.CreateShortcut($ShortcutPath)
  $Shortcut.TargetPath = $Target
  $Shortcut.Arguments = $Arguments
  $Shortcut.WorkingDirectory = $InstallRoot
  $Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
  $Shortcut.Save()
}

Write-Output "Installed to: $InstallRoot"
Write-Output "Data dir: $DataRoot"
Write-Output "Desktop shortcuts created."
Write-Output "Open: http://127.0.0.1:$Port/?v=desktop"
