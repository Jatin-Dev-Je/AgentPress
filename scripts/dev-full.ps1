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

Start-Process -FilePath 'powershell' -ArgumentList $backendArgs -WorkingDirectory $RepoRoot
Start-Process -FilePath 'powershell' -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $RepoRoot 'frontend')

Write-Host "Launched. Frontend: http://localhost:$FrontendPort  Backend: http://localhost:$BackendPort" -ForegroundColor Green
