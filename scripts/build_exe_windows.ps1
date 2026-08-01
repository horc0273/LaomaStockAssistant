param(
  [string]$Version = (Get-Date -Format "yyyyMMdd-HHmm")
)

$ErrorActionPreference = "Stop"

$SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DistRoot = Join-Path $SourceRoot "dist"
$BuildRoot = Join-Path $SourceRoot "build"
$Name = "LaomaStockAssistant"
$ReleaseName = "LaomaStockAssistant-Exe-$Version"
$ReleaseRoot = Join-Path $DistRoot $ReleaseName
$ZipPath = Join-Path $DistRoot "$ReleaseName.zip"

New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null

if (Test-Path $ReleaseRoot) { Remove-Item -LiteralPath $ReleaseRoot -Recurse -Force }
if (Test-Path $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }

python -m pip show pyinstaller | Out-Null
python (Join-Path $PSScriptRoot "create_app_icon.py")

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name $Name `
  --icon "assets\laoma-stock.ico" `
  --version-file "packaging\version_info.txt" `
  --add-data "static;static" `
  --hidden-import "app.main" `
  --hidden-import "app.ai_service" `
  --hidden-import "app.auth_service" `
  --hidden-import "app.data_provider" `
  --hidden-import "app.quant_engine" `
  --hidden-import "app.tushare_service" `
  --hidden-import "app.infrastructure" `
  --hidden-import "app.market_intelligence" `
  --hidden-import "app.market_data_gateway" `
  --hidden-import "app.screener_service" `
  --hidden-import "app.abnormal_service" `
  --hidden-import "app.industry_chain_service" `
  --hidden-import "app.recommendation_scoring_service" `
  --hidden-import "app.akshare_service" `
  --hidden-import "app.backtest_service" `
  --hidden-import "redis" `
  --collect-all "psycopg" `
  --collect-all "psycopg_binary" `
  desktop_launcher.py

Copy-Item -LiteralPath (Join-Path $DistRoot $Name) -Destination $ReleaseRoot -Recurse -Force

$Readme = @(
  "Laoma Stock Assistant EXE package",
  "",
  "Run:",
  "1. Extract this zip.",
  "2. Double click LaomaStockAssistant.exe.",
  "3. Browser opens automatically.",
  "",
  "Data:",
  "- Local data is stored in %APPDATA%\LaomaStockAssistant.",
  "- This package does NOT include author positions, watchlist, Tushare token, or member database.",
  "",
  "Login:",
  "- Default admin username: laoma",
  "- Default admin password: maguo591034",
  "",
  "Network:",
  "- The app needs internet access for market data.",
  "- If Windows Firewall asks, allow network access.",
  "- Desktop opens locally on this PC.",
  "- Mobile on the same Wi-Fi can visit: http://<your-computer-LAN-IP>:8788/?v=desktop"
)
Set-Content -LiteralPath (Join-Path $ReleaseRoot "README-FOR-TESTERS.txt") -Encoding ASCII -Value $Readme

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($ReleaseRoot, $ZipPath)

Write-Output "EXE folder: $ReleaseRoot"
Write-Output "EXE zip: $ZipPath"
