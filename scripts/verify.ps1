$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$gatewayPython = Join-Path $projectRoot "services/gateway/.venv/Scripts/python.exe"
$evaluationPython = Join-Path $projectRoot "services/evaluation/.venv/Scripts/python.exe"

if (-not (Test-Path $gatewayPython) -or -not (Test-Path $evaluationPython)) {
    throw "Local virtual environments are missing. Run scripts/setup-local.ps1 first."
}

Push-Location $projectRoot
try {
    & $gatewayPython -m unittest discover -s services/gateway/tests -v
    & $evaluationPython -m unittest discover -s services/evaluation/tests -v
    & $gatewayPython -m unittest discover -s sdk/python/tests -v
    & $gatewayPython -m unittest discover -s tests/experiments -v
    & $gatewayPython -m unittest discover -s tests/gateway -v
    & $evaluationPython -m unittest discover -s tests/evaluation -v
    & $gatewayPython -m unittest discover -s tests/integration -v
    & $gatewayPython experiments/run_experiments.py
    npm --prefix web/gateway run build
    npm --prefix web/evaluation run build
} finally {
    Pop-Location
}
