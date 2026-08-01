param(
  [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$IsccCandidates = @(
  (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
  "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
  throw "Inno Setup 6 not found."
}

Push-Location $SourceRoot
try {
  python -m compileall app desktop_launcher.py
  node --check static\app.js
  powershell -ExecutionPolicy Bypass -File .\scripts\build_exe_windows.ps1 -Version $Version
  & $Iscc "/DMyAppVersion=$Version" "/DSourceReleaseName=LaomaStockAssistant-Exe-$Version" ".\packaging\LaomaStockAssistant.iss"
  if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
  }
} finally {
  Pop-Location
}

$SetupPath = Join-Path $SourceRoot "dist\formal\LaomaStockAssistant-Setup-$Version.exe"
Write-Output "Formal installer: $SetupPath"
