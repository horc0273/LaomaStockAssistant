param(
  [int]$Port = 8788,
  [string]$HostName = "0.0.0.0"
)

$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent $PSScriptRoot
$DataRoot = Join-Path $env:APPDATA "LaomaStockAssistant"
$VenvRoot = Join-Path $DataRoot ".venv"
$PythonExe = Join-Path $VenvRoot "Scripts\python.exe"
$Url = "http://127.0.0.1:$Port/?v=desktop"
$LanUrl = $null

New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null

if (-not (Test-Path $PythonExe)) {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv $VenvRoot
  } else {
    python -m venv $VenvRoot
  }
}

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r (Join-Path $AppRoot "requirements.txt")

$env:LAOMA_STOCK_DATA_DIR = $DataRoot
$env:PYTHONUTF8 = "1"
$env:LAOMA_BIND_HOST = $HostName

if ($HostName -eq "0.0.0.0") {
  try {
    $LanIp = (Get-NetIPAddress -AddressFamily IPv4 |
      Where-Object {
        $_.IPAddress -notlike '127.*' -and
        $_.IPAddress -notlike '169.254.*' -and
        $_.PrefixOrigin -ne 'WellKnown'
      } |
      Sort-Object InterfaceMetric |
      Select-Object -First 1 -ExpandProperty IPAddress)
    if ($LanIp) {
      $LanUrl = "http://$LanIp`:$Port/?v=desktop"
    }
  } catch {
  }
}

Start-Process $Url | Out-Null
if ($LanUrl) {
  Write-Host "LAN access: $LanUrl"
}
& $PythonExe -m uvicorn app.main:app --host $HostName --port $Port
