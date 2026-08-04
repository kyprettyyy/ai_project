$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.runtime'

if (Test-Path -LiteralPath $runtimeDir) {
    Get-ChildItem -LiteralPath $runtimeDir -Filter '*.pid' -File | ForEach-Object {
        $savedPid = [int](Get-Content -LiteralPath $_.FullName)
        $process = Get-Process -Id $savedPid -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $savedPid
            Write-Host "Stopped $($_.BaseName) (PID $savedPid)."
        }
        Remove-Item -LiteralPath $_.FullName
    }
}

Set-Location $projectRoot
docker compose down
