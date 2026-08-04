$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$gatewayDir = Join-Path $projectRoot 'services\gateway'
$evaluationDir = Join-Path $projectRoot 'services\evaluation'
$gatewayWebDir = Join-Path $projectRoot 'web\gateway'
$evaluationWebDir = Join-Path $projectRoot 'web\evaluation'
$pythonCommand = (Get-Command python.exe -ErrorAction Stop).Source
$npmCommand = (Get-Command npm.cmd -ErrorAction Stop).Source

if (-not (Test-Path -LiteralPath (Join-Path $gatewayDir '.venv\Scripts\python.exe'))) {
    & $pythonCommand -m venv (Join-Path $gatewayDir '.venv')
}
& (Join-Path $gatewayDir '.venv\Scripts\python.exe') -m pip install -r (Join-Path $gatewayDir 'requirements.txt')

if (-not (Test-Path -LiteralPath (Join-Path $evaluationDir '.venv\Scripts\python.exe'))) {
    & $pythonCommand -m venv (Join-Path $evaluationDir '.venv')
}
& (Join-Path $evaluationDir '.venv\Scripts\python.exe') -m pip install -r (Join-Path $evaluationDir 'requirements.txt')

Push-Location $gatewayWebDir
try {
    & $npmCommand ci --legacy-peer-deps
} finally {
    Pop-Location
}

Push-Location $evaluationWebDir
try {
    & $npmCommand ci --legacy-peer-deps
} finally {
    Pop-Location
}

Write-Host 'Local Python and Node dependencies are ready.'
