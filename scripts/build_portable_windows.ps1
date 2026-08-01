param(
  [switch]$IncludeCurrentData
)

$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent $PSScriptRoot
$DistRoot = Join-Path $SourceRoot "dist\LaomaStockAssistant"

if (Test-Path $DistRoot) {
  Remove-Item -LiteralPath $DistRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null

$excludeDirs = @("__pycache__", ".venv", "dist")
$excludeFiles = @("server.out.log", "server.err.log")

Get-ChildItem -LiteralPath $SourceRoot -Force | ForEach-Object {
  if ($excludeDirs -contains $_.Name) { return }
  if ($excludeFiles -contains $_.Name) { return }
  if ($_.Name -eq "data" -and -not $IncludeCurrentData) { return }
  $dest = Join-Path $DistRoot $_.Name
  if ($_.PSIsContainer) {
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force
  } else {
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
  }
}

$CmdPath = Join-Path $DistRoot "Start-LaomaStockAssistant.cmd"
Set-Content -LiteralPath $CmdPath -Encoding ASCII -Value "@echo off`r`npowershell.exe -ExecutionPolicy Bypass -NoProfile -File `"%~dp0scripts\run_windows.ps1`"`r`npause`r`n"

Write-Output "Portable package created: $DistRoot"
Write-Output "Run: $CmdPath"
