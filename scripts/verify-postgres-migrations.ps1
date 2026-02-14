param(
  [string]$PostgresImage = 'postgres:16',
  [int]$Port = 55432,
  [string]$DbUser = 'agentpress',
  [string]$DbPassword = 'agentpress',
  [string]$DbName = 'agentpress'
)

$ErrorActionPreference = 'Stop'

function Assert-DockerRunning {
  $null = & docker info 2>$null
  if ($LASTEXITCODE -ne 0) {
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

function Invoke-Docker {
  param(
    [Parameter(Mandatory=$true)][string[]]$Args,
    [string]$OnFailMessage = 'Docker command failed.'
  )
  $out = & docker @Args 2>&1
  if ($LASTEXITCODE -ne 0) {
    $msg = ($out | Out-String).Trim()
    $cmdLine = 'docker ' + ($Args -join ' ')
    throw "$OnFailMessage`n`ncmd: $cmdLine`nexit: $LASTEXITCODE`noutput:`n$msg"
  }
  return $out
}

function Test-ContainerExists {
  param([Parameter(Mandatory=$true)][string]$Name)
  $id = (& docker ps -aq --filter "name=^${Name}$" | Select-Object -First 1)
  return -not [string]::IsNullOrWhiteSpace($id)
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
  Invoke-Docker -Args @('pull', $PostgresImage) -OnFailMessage "Failed to pull $PostgresImage."

  Write-Host "Starting Postgres container $containerName on port $Port"
  try {
    Invoke-Docker -Args @(
      'run','-d',
      '--name', $containerName,
      '-e', "POSTGRES_USER=$DbUser",
      '-e', "POSTGRES_PASSWORD=$DbPassword",
      '-e', "POSTGRES_DB=$DbName",
      '-p', "${Port}:5432",
      $PostgresImage
    ) -OnFailMessage "Failed to start Postgres container. This can happen if Docker Desktop's disk image has an I/O issue."
  } catch {
    Write-Host "--- docker system df (debug) ---"
    try { docker system df } catch {}
    Write-Host "-------------------------------"
    throw
  }

  if (-not (Test-ContainerExists -Name $containerName)) {
    throw "Postgres container was not created (name=$containerName)."
  }

  Write-Host 'Waiting for Postgres readiness (pg_isready)'
  $deadline = (Get-Date).AddSeconds(60)
  while ((Get-Date) -lt $deadline) {
    try {
      & docker exec $containerName pg_isready -U $DbUser -d $DbName | Out-Null
      if ($LASTEXITCODE -eq 0) {
        break
      }
      break
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }

  # If still not ready, dump logs and fail.
  try {
    & docker exec $containerName pg_isready -U $DbUser -d $DbName | Out-Null
    if ($LASTEXITCODE -ne 0) {
      Write-Host "--- postgres logs (debug) ---"
      try { docker logs --tail 200 $containerName } catch {}
      Write-Host "----------------------------"
      throw "Postgres did not become ready in time."
    }
  } catch {
    Write-Host "--- postgres logs (debug) ---"
    try { docker logs --tail 200 $containerName } catch {}
    Write-Host "----------------------------"
    throw
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
