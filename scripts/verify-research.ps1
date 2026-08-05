$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $projectRoot
try {
    python -m unittest discover -s tests/gateway -p test_routing.py -v
    python -m unittest discover -s tests/evaluation -v
    python -m unittest discover -s tests/experiments -v
    python -m unittest discover -s tests/integration -v
    python experiments/run_experiments.py
} finally {
    Pop-Location
}
