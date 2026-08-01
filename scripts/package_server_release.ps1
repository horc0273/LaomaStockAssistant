$ErrorActionPreference = 'Stop'
$source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$root = (Resolve-Path (Join-Path $source '..')).Path
$name = 'LaomaStockAssistant-Server-1.6.9-TSignal-MorningBrief'
$stage = Join-Path $root $name
$zip = Join-Path $root ($name + '.zip')

if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
New-Item -ItemType Directory -Path $stage -Force | Out-Null

$excluded = @('dist', '__pycache__', 'data', 'server.err.log', 'server.out.log', 'server-v2.err.log', 'server-v2.out.log', 'server-v3.err.log', 'server-v3.out.log', 'server-open-source.err.log', 'server-open-source.out.log')
Get-ChildItem -LiteralPath $source -Force |
  Where-Object { $_.Name -notin $excluded } |
  Copy-Item -Destination $stage -Recurse -Force

New-Item -ItemType Directory -Path (Join-Path $stage 'data') -Force | Out-Null
Set-Content -LiteralPath (Join-Path $stage 'data/.gitkeep') -Value '' -Encoding utf8
Get-ChildItem -LiteralPath $stage -Directory -Recurse -Force -Filter '__pycache__' | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $stage -File -Recurse -Force | Where-Object { $_.Extension -in @('.pyc', '.pyo') } | Remove-Item -Force

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($stage, $zip)
Write-Output "PACKAGE=$zip"
Write-Output "SIZE=$((Get-Item -LiteralPath $zip).Length)"
Write-Output "FILES=$((Get-ChildItem -LiteralPath $stage -File -Recurse).Count)"
