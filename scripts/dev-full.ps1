param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 3000,
  [switch]$AutoBackendPort,
  [ValidateSet('manual','auto','disabled')]
  [string]$ToolMode = 'manual',
  [string]$OllamaModel = 'llama3.2:1b',
  [string]$OllamaBaseUrl = 'http://localhost:11434',
  [switch]$NoReload
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot

if ($AutoBackendPort) {
  $originalPort = $BackendPort
  for ($i = 0; $i -lt 20; $i++) {
    $inUse = @(Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue).Count -gt 0
    if (-not $inUse) { break }
    $BackendPort++
  }
  if ($BackendPort -ne $originalPort) {
    Write-Host "Backend port :$originalPort is in use; using :$BackendPort instead" -ForegroundColor Yellow
  }
}

Write-Host "Starting backend on :$BackendPort and frontend on :$FrontendPort" -ForegroundColor Cyan

$backendAlreadyUp = $false
$backendLooksLikeAgentpress = $false
try {
  $backendAlreadyUp = Test-NetConnection -ComputerName 'localhost' -Port $BackendPort -InformationLevel Quiet
  if ($backendAlreadyUp) {
    $health = Invoke-RestMethod -Uri "http://localhost:$BackendPort/health" -Method Get -TimeoutSec 2
    if ($health -and $health.status -and $health.plugins_dir -and $health.version) {
      $backendLooksLikeAgentpress = $true
    }
  }
} catch {
  # ignore
}

$frontendLockPath = Join-Path $RepoRoot 'frontend\.next\dev\lock'
$frontendAlreadyUp = Test-Path $frontendLockPath

$backendCommand = (
  "Set-Location '$RepoRoot'; ./scripts/dev.ps1 -Port $BackendPort -ToolMode $ToolMode -OllamaModel '$OllamaModel' -OllamaBaseUrl '$OllamaBaseUrl'" +
  ($(if ($NoReload) { ' -NoReload' } else { '' }))
)
$backendArgs = @(
  '-NoProfile',
  '-ExecutionPolicy',
  'Bypass',
  '-Command',
  $backendCommand
)

$frontendCommand = "Set-Location '$RepoRoot/frontend'; if (-not (Test-Path node_modules)) { npm install }; `$env:PORT='$FrontendPort'; `$env:NEXT_PUBLIC_BACKEND_URL='http://localhost:$BackendPort'; npm run dev"
$frontendArgs = @(
  '-NoProfile',
  '-ExecutionPolicy',
  'Bypass',
  '-Command',
  $frontendCommand
)

if ($backendAlreadyUp -and $backendLooksLikeAgentpress) {
  Write-Host "Backend already running on :$BackendPort (skipping)" -ForegroundColor Yellow
} elseif ($backendAlreadyUp -and -not $backendLooksLikeAgentpress) {
  Write-Host "Port :$BackendPort is already in use, but it doesn't look like Agentpress. Stop whatever is using the port, then re-run this script." -ForegroundColor Red
} else {
  Start-Process -FilePath 'powershell' -ArgumentList $backendArgs -WorkingDirectory $RepoRoot
}

if ($frontendAlreadyUp) {
  Write-Host "Frontend already running (lock present). If you want to restart it, close the existing next dev process and delete $frontendLockPath" -ForegroundColor Yellow
} else {
  Start-Process -FilePath 'powershell' -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $RepoRoot 'frontend')
}

Write-Host "Launched. Frontend: http://localhost:$FrontendPort  Backend: http://localhost:$BackendPort" -ForegroundColor Green
