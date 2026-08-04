$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.runtime'
$gatewayDir = Join-Path $projectRoot 'services\gateway'
$evaluationDir = Join-Path $projectRoot 'services\evaluation'
$gatewayWebDir = Join-Path $projectRoot 'web\gateway'
$evaluationWebDir = Join-Path $projectRoot 'web\evaluation'
$platformWebDir = Join-Path $projectRoot 'platform-web'

Set-Location $projectRoot
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
if (-not (Test-Path -LiteralPath (Join-Path $gatewayDir '.env'))) {
    Copy-Item -LiteralPath (Join-Path $gatewayDir '.env.example') -Destination (Join-Path $gatewayDir '.env')
}
if (-not (Test-Path -LiteralPath (Join-Path $evaluationDir '.env'))) {
    Copy-Item -LiteralPath (Join-Path $evaluationDir '.env.example') -Destination (Join-Path $evaluationDir '.env')
}

$gatewayPython = Join-Path $gatewayDir '.venv\Scripts\python.exe'
$evaluationPython = Join-Path $evaluationDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $gatewayPython) -or -not (Test-Path -LiteralPath $evaluationPython)) {
    throw 'Python virtual environments are missing. Run .\scripts\setup-local.ps1 first.'
}
if (-not (Test-Path -LiteralPath (Join-Path $gatewayWebDir 'node_modules')) -or
    -not (Test-Path -LiteralPath (Join-Path $evaluationWebDir 'node_modules'))) {
    throw 'Node dependencies are missing. Run .\scripts\setup-local.ps1 first.'
}

docker compose up -d

function Start-ManagedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )

    $pidPath = Join-Path $runtimeDir "$Name.pid"
    if (Test-Path -LiteralPath $pidPath) {
        $savedPid = [int](Get-Content -LiteralPath $pidPath)
        if (Get-Process -Id $savedPid -ErrorAction SilentlyContinue) {
            Write-Host "$Name is already running (PID $savedPid)."
            return
        }
        Remove-Item -LiteralPath $pidPath
    }

    $stdoutPath = Join-Path $runtimeDir "$Name.out.log"
    $stderrPath = Join-Path $runtimeDir "$Name.err.log"
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    Set-Content -LiteralPath $pidPath -Value $process.Id
    Write-Host "Started $Name (PID $($process.Id))."
}

function Wait-HttpEndpoint {
    param([string]$Name, [string]$Uri)
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "$Name is ready: $Uri"
                return
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "$Name did not become ready. Check .runtime\$Name.err.log."
}

Start-ManagedProcess -Name 'gateway' -FilePath $gatewayPython `
    -Arguments @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8123') `
    -WorkingDirectory $gatewayDir
Wait-HttpEndpoint -Name 'gateway' -Uri 'http://127.0.0.1:8123/api/health/'

Start-ManagedProcess -Name 'evaluation' -FilePath $evaluationPython `
    -Arguments @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8124') `
    -WorkingDirectory $evaluationDir
Wait-HttpEndpoint -Name 'evaluation' -Uri 'http://127.0.0.1:8124/api/health'

$npmCommand = (Get-Command npm.cmd -ErrorAction Stop).Source
Start-ManagedProcess -Name 'gateway-web' -FilePath $npmCommand `
    -Arguments @('run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173') `
    -WorkingDirectory $gatewayWebDir
Start-ManagedProcess -Name 'evaluation-web' -FilePath $npmCommand `
    -Arguments @('run', 'dev', '--', '--host', '127.0.0.1', '--port', '5174') `
    -WorkingDirectory $evaluationWebDir

Wait-HttpEndpoint -Name 'gateway-web' -Uri 'http://127.0.0.1:5173/'
Wait-HttpEndpoint -Name 'evaluation-web' -Uri 'http://127.0.0.1:5174/'

Start-ManagedProcess -Name 'platform-web' -FilePath $gatewayPython `
    -Arguments @('-m', 'http.server', '5172', '--bind', '127.0.0.1') `
    -WorkingDirectory $platformWebDir
Wait-HttpEndpoint -Name 'platform-web' -Uri 'http://127.0.0.1:5172/'

docker compose ps
Write-Host 'EvalRoute local development environment is ready: http://127.0.0.1:5172/'
