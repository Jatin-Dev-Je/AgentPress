param(
  [Parameter(Mandatory=$true)][string]$DatabaseUrl,
  [string]$Revision = 'head'
)

$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendDir = Join-Path $root 'backend'
$alembicExe = Join-Path $root '.venv\Scripts\alembic.exe'

if (-not (Test-Path $alembicExe)) {
  throw "Alembic not found at $alembicExe. Install deps: ./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt"
}

Write-Host "WARNING: This will set alembic_version to '$Revision' WITHOUT running migrations." -ForegroundColor Yellow
Write-Host "Only use this if the database schema already matches the migration history." -ForegroundColor Yellow
Write-Host "Database: $DatabaseUrl" -ForegroundColor Yellow

$confirm = Read-Host "Type STAMP to continue"
if ($confirm -ne 'STAMP') {
  throw 'Aborted.'
}

$env:AGENTPRESS_DATABASE_URL = $DatabaseUrl

Push-Location $backendDir
try {
  & $alembicExe stamp $Revision
  & $alembicExe current
  Write-Host 'STAMP COMPLETE'
} finally {
  Pop-Location
}
