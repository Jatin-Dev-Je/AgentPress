param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 3000,
  [ValidateSet('manual','auto','disabled')]
  [string]$ToolMode = 'manual',
  [string]$OllamaModel = 'llama3',
  [string]$OllamaBaseUrl = 'http://localhost:11434',
  [switch]$NoReload
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "Starting backend on :$BackendPort and frontend on :$FrontendPort" -ForegroundColor Cyan

$backendAlreadyUp = $false
try {
  $backendAlreadyUp = Test-NetConnection -ComputerName 'localhost' -Port $BackendPort -InformationLevel Quiet
} catch {
  $backendAlreadyUp = $false
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

$frontendCommand = "Set-Location '$RepoRoot/frontend'; if (-not (Test-Path node_modules)) { npm install }; `$env:PORT='$FrontendPort'; npm run dev"
$frontendArgs = @(
  '-NoProfile',
  '-ExecutionPolicy',
  'Bypass',
  '-Command',
  $frontendCommand
)

if ($backendAlreadyUp) {
  Write-Host "Backend already running on :$BackendPort (skipping)" -ForegroundColor Yellow
} else {
  Start-Process -FilePath 'powershell' -ArgumentList $backendArgs -WorkingDirectory $RepoRoot
}

if ($frontendAlreadyUp) {
  Write-Host "Frontend already running (lock present). If you want to restart it, close the existing next dev process and delete $frontendLockPath" -ForegroundColor Yellow
} else {
  Start-Process -FilePath 'powershell' -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $RepoRoot 'frontend')
}

Write-Host "Launched. Frontend: http://localhost:$FrontendPort  Backend: http://localhost:$BackendPort" -ForegroundColor Green
