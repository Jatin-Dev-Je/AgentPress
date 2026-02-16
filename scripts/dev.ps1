param(
  [int]$Port = 8000,
  [switch]$AutoPort,
  [ValidateSet('manual','auto','disabled')]
  [string]$ToolMode = 'manual',
  [string]$OllamaModel = 'llama3',
  [string]$OllamaBaseUrl = 'http://127.0.0.1:11434',
  [switch]$NoReload
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$VenvDir = Join-Path $RepoRoot ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
  python -m venv $VenvDir
}

& $PythonExe -m pip install -U pip
& $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt")

$DataDir = Join-Path $RepoRoot ".data"
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null

if ($AutoPort) {
  $originalPort = $Port
  for ($i = 0; $i -lt 20; $i++) {
    $inUse = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).Count -gt 0
    if (-not $inUse) {
      break
    }
    $Port++
  }
  if ($Port -ne $originalPort) {
    Write-Host "Port :$originalPort is in use; using :$Port instead" -ForegroundColor Yellow
  }
}

Push-Location $BackendDir
try {
  $env:AGENTPRESS_DATABASE_URL = "sqlite+aiosqlite:///../.data/agentpress.db"
  $env:AGENTPRESS_TOOL_CALLING_MODE = $ToolMode
  $env:AGENTPRESS_LLM_PROVIDER = "ollama"
  $env:AGENTPRESS_OLLAMA_MODEL = $OllamaModel
  $env:AGENTPRESS_OLLAMA_BASE_URL = $OllamaBaseUrl
  $uvicornArgs = @('app.main:app', '--port', "$Port")
  if (-not $NoReload) {
    $uvicornArgs += '--reload'
  }
  & $PythonExe -m uvicorn @uvicornArgs
} finally {
  Pop-Location
}
