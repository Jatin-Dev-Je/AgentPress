$ErrorActionPreference = 'Stop'

function Wait-ForHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 3
            if ($resp -and $resp.status -eq 'ok') { return $resp }
        } catch {
            Start-Sleep -Milliseconds 300
        }
    }

    throw "Backend health check timed out: $Url"
}

function Assert-True {
    param(
        $Condition,
        [string]$Message
    )
    if (-not $Condition) { throw "ASSERT FAILED: $Message" }
}

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendDir = Join-Path $root 'backend'
$pythonExe = Join-Path $root '.venv\Scripts\python.exe'

$baseUrl = $env:AGENTPRESS_BASE_URL
if ([string]::IsNullOrWhiteSpace($baseUrl)) { $baseUrl = 'http://127.0.0.1:8000' }

$healthUrl = "$baseUrl/health"

$serverProc = $null
$startedServer = $false

try {
    $portOpen = $false
    try {
        $portCheck = Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -WarningAction SilentlyContinue
        $portOpen = [bool]$portCheck.TcpTestSucceeded
    } catch {
        $portOpen = $false
    }

    if (-not $portOpen) {
        if (-not (Test-Path $pythonExe)) {
            throw "Python venv not found at $pythonExe. Create it first or run ./scripts/dev.ps1"
        }

        $env:AGENTPRESS_DATABASE_URL = 'sqlite+aiosqlite:///./.data/agentpress.db'

        $serverProc = Start-Process -FilePath $pythonExe -WorkingDirectory $backendDir -PassThru -WindowStyle Hidden -ArgumentList @(
            '-m','uvicorn','app.main:app','--port','8000'
        )
        $startedServer = $true
    }

    $health = Wait-ForHealth -Url $healthUrl -TimeoutSeconds 30
    Write-Host "OK /health (plugins_dir=$($health.plugins_dir))"

    $agentName = "Smoke Agent $(Get-Date -Format 'yyyyMMdd-HHmmss')"
    $agent = Invoke-RestMethod -Method Post -Uri "$baseUrl/agents" -ContentType 'application/json' -Body (@{
        name = $agentName
        model = 'ollama'
        system_prompt = 'You are helpful.'
        temperature = 0.7
    } | ConvertTo-Json)

    Assert-True ($agent.id) 'agent create returned id'
    Assert-True ($agent.name -eq $agentName) 'agent name matches'

    $agent2 = Invoke-RestMethod -Method Get -Uri "$baseUrl/agents/$($agent.id)"
    Assert-True ($agent2.id -eq $agent.id) 'agent get matches id'

    $agent3 = Invoke-RestMethod -Method Put -Uri "$baseUrl/agents/$($agent.id)" -ContentType 'application/json' -Body (@{
        name = "${agentName} (updated)"
        temperature = 0.2
    } | ConvertTo-Json)
    Assert-True ($agent3.name -like '*updated*') 'agent update persisted'

    $sse = Invoke-WebRequest -Method Post -Uri "$baseUrl/agents/$($agent.id)/chat" -ContentType 'application/json' -Body (@{
        message = '/tool echo echo {"text":"hello"}'
    } | ConvertTo-Json) | Select-Object -ExpandProperty Content

    Assert-True ($sse -match 'event: tool_call_start') 'SSE includes tool_call_start'
    Assert-True ($sse -match 'event: tool_call_end') 'SSE includes tool_call_end'
    Assert-True ($sse -match '"text":"hello"') 'SSE token includes echoed text'
    Write-Host 'OK chat SSE + /tool echo'

    $plugins = Invoke-RestMethod -Method Get -Uri "$baseUrl/plugins"
    $echo = $plugins | Where-Object { $_.id -eq 'echo' } | Select-Object -First 1
    Assert-True ($null -ne $echo) 'echo plugin is installed'

    $toolRes = Invoke-RestMethod -Method Post -Uri "$baseUrl/plugins/echo/tools/echo" -ContentType 'application/json' -Headers @{ 'x-agent-id' = $agent.id } -Body (@{
        params = @{ text = 'hi' }
    } | ConvertTo-Json)
    Assert-True ($toolRes.result) 'plugin tool call returned result'
    Write-Host 'OK plugins echo tool'

    Write-Host 'SMOKE PASSED'
    exit 0
}
finally {
    if ($startedServer -and $serverProc) {
        try {
            Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
        } catch {
            # ignore
        }
    }
}
