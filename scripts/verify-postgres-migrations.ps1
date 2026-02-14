param(
  [string]$PostgresImage = 'postgres:16',
  [int]$Port = 55432,
  [string]$DbUser = 'agentpress',
  [string]$DbPassword = 'agentpress',
  [string]$DbName = 'agentpress'
)

$ErrorActionPreference = 'Stop'

function Assert-DockerRunning {
  try {
    docker info | Out-Null
  } catch {
    throw @"
Docker Engine is not reachable.

Start Docker Desktop, wait until it shows 'Running', then re-run:
  ./scripts/verify-postgres-migrations.ps1

If you use a non-default Docker context, also verify:
  docker context ls
  docker context use desktop-linux
"@
  }
}

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendDir = Join-Path $root 'backend'
$pythonExe = Join-Path $root '.venv\Scripts\python.exe'
$alembicExe = Join-Path $root '.venv\Scripts\alembic.exe'

if (-not (Test-Path $pythonExe)) {
  throw "Python venv not found at $pythonExe. Run ./scripts/dev.ps1 first."
}
if (-not (Test-Path $alembicExe)) {
  throw "Alembic not found at $alembicExe. Install deps: $pythonExe -m pip install -r backend/requirements.txt"
}

Assert-DockerRunning

$containerName = "agentpress-migtest-postgres-$([Guid]::NewGuid().ToString('N').Substring(0,8))"

try {
  Write-Host "Pulling $PostgresImage (if needed)"
  docker pull $PostgresImage | Out-Null

  Write-Host "Starting Postgres container $containerName on port $Port"
  docker run -d --name $containerName `
    -e "POSTGRES_USER=$DbUser" `
    -e "POSTGRES_PASSWORD=$DbPassword" `
    -e "POSTGRES_DB=$DbName" `
    -p "${Port}:5432" `
    $PostgresImage | Out-Null

  Write-Host 'Waiting for Postgres readiness (pg_isready)'
  $deadline = (Get-Date).AddSeconds(60)
  while ((Get-Date) -lt $deadline) {
    try {
      docker exec $containerName pg_isready -U $DbUser -d $DbName | Out-Null
      break
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }

  $dbUrl = "postgresql+asyncpg://${DbUser}:${DbPassword}@127.0.0.1:${Port}/${DbName}"
  $env:AGENTPRESS_DATABASE_URL = $dbUrl

  Push-Location $backendDir
  try {
    Write-Host 'Running alembic upgrade head'
    & $alembicExe upgrade head

    Write-Host 'Checking current revision'
    & $alembicExe current

    Write-Host 'Validating tables exist'
    & $pythonExe -c @"
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("$dbUrl")
    try:
        rows = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public'
            ORDER BY table_name
        """)
        names = {r['table_name'] for r in rows}
        required = {'agents','conversations','messages','tool_calls','alembic_version'}
        missing = sorted(required - names)
        if missing:
            raise SystemExit(f"Missing tables: {missing}; got: {sorted(names)}")
        print("OK tables present")
    finally:
        await conn.close()

asyncio.run(main())
"@

    Write-Host 'Running downgrade base (destructive)'
    & $alembicExe downgrade base

    Write-Host 'Re-upgrade head (idempotency)'
    & $alembicExe upgrade head

    Write-Host 'POSTGRES MIGRATIONS VERIFIED'
  } finally {
    Pop-Location
  }
}
finally {
  if ($containerName) {
    try {
      docker rm -f $containerName | Out-Null
    } catch {
      # ignore
    }
  }
}
