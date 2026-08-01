param(
  [string]$Version = (Get-Date -Format "yyyyMMdd-HHmm")
)

$ErrorActionPreference = "Stop"

$SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DistRoot = Join-Path $SourceRoot "dist"
$PackageName = "LaomaStockAssistant-Setup-$Version"
$StageRoot = Join-Path $env:TEMP $PackageName
$PackageRoot = Join-Path $DistRoot $PackageName
$ZipPath = Join-Path $DistRoot "$PackageName.zip"

if (Test-Path $StageRoot) {
  Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
if (Test-Path $PackageRoot) {
  Remove-Item -LiteralPath $PackageRoot -Recurse -Force
}
if (Test-Path $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}

New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null
New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null

foreach ($dir in @("app", "static", "scripts")) {
  Copy-Item -LiteralPath (Join-Path $SourceRoot $dir) -Destination (Join-Path $StageRoot $dir) -Recurse -Force
}
foreach ($file in @("requirements.txt", "README.md", "INSTALL_WINDOWS.md", ".env.example")) {
  $sourceFile = Join-Path $SourceRoot $file
  if (Test-Path $sourceFile) {
    Copy-Item -LiteralPath $sourceFile -Destination (Join-Path $StageRoot $file) -Force
  }
}

Get-ChildItem -LiteralPath $StageRoot -Directory -Recurse -Force -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $StageRoot -File -Recurse -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
  Remove-Item -Force

$InstallCmd = Join-Path $StageRoot "Install-LaomaStockAssistant.cmd"
Set-Content -LiteralPath $InstallCmd -Encoding ASCII -Value "@echo off`r`ncd /d `"%~dp0`"`r`npowershell.exe -ExecutionPolicy Bypass -NoProfile -File `"%~dp0scripts\install_windows_local.ps1`"`r`necho.`r`necho Install finished. You can launch Laoma Stock Assistant from the desktop shortcut.`r`npause`r`n"

$StartCmd = Join-Path $StageRoot "Start-Without-Install.cmd"
Set-Content -LiteralPath $StartCmd -Encoding ASCII -Value "@echo off`r`ncd /d `"%~dp0`"`r`npowershell.exe -ExecutionPolicy Bypass -NoProfile -File `"%~dp0scripts\run_windows.ps1`"`r`npause`r`n"

$TesterReadme = Join-Path $StageRoot "README-FOR-TESTERS.txt"
$ReadmeLines = @(
  "Laoma Stock Assistant - Internal Test Installer",
  "",
  "Install:",
  "1. Extract the whole zip package.",
  "2. Double click Install-LaomaStockAssistant.cmd.",
  "3. Desktop shortcuts will be created after install.",
  "4. Double click the desktop shortcut. Browser will open http://127.0.0.1:8788/?v=desktop.",
  "",
  "First launch:",
  "- The app creates a Python virtual environment and installs dependencies on first launch.",
  "- Internet access is required. First launch may take 1-5 minutes.",
  "- If Windows Firewall asks, allow Python / PowerShell network access.",
  "",
  "Login:",
  "- Default admin username: laoma",
  "- Default admin password: maguo591034",
  "- Internal test users can start with the default account.",
  "",
  "Data isolation:",
  "- Local data is stored in %APPDATA%\LaomaStockAssistant.",
  "- This installer does NOT include the author's positions, watchlist, Tushare token, or member database.",
  "",
  "Market data:",
  "- Without Tushare token, the app uses public Tencent/Eastmoney data sources.",
  "- To enable Tushare daily K-line, put tushare_token.txt into %APPDATA%\LaomaStockAssistant.",
  "",
  "Disclaimer:",
  "Research and strategy validation only. Not investment advice."
)
Set-Content -LiteralPath $TesterReadme -Encoding ASCII -Value $ReadmeLines

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($StageRoot, $ZipPath)
New-Item -ItemType Directory -Force -Path $PackageRoot | Out-Null
Copy-Item -Path (Join-Path $StageRoot "*") -Destination $PackageRoot -Recurse -Force

Write-Output "Release folder: $PackageRoot"
Write-Output "Release zip: $ZipPath"
