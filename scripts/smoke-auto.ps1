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

function Test-Ollama {
    param(
        [string]$BaseUrl
    )
    $tagsUrl = ($BaseUrl.TrimEnd('/') + '/api/tags')
    try {
        return Invoke-RestMethod -Method Get -Uri $tagsUrl -TimeoutSec 3
    } catch {
        return $null
    }
}

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendDir = Join-Path $root 'backend'
$pythonExe = Join-Path $root '.venv\Scripts\python.exe'

$ollamaBaseUrl = $env:AGENTPRESS_OLLAMA_BASE_URL
if ([string]::IsNullOrWhiteSpace($ollamaBaseUrl)) { $ollamaBaseUrl = 'http://localhost:11434' }

$tags = Test-Ollama -BaseUrl $ollamaBaseUrl
if (-not $tags) {
    Write-Host "SKIP: Ollama not reachable at $ollamaBaseUrl"
    exit 0
}

$modelName = $env:AGENTPRESS_AUTO_SMOKE_MODEL
if ([string]::IsNullOrWhiteSpace($modelName)) {
    $modelName = ($tags.models | Select-Object -First 1).name
}

if ([string]::IsNullOrWhiteSpace($modelName)) {
    Write-Host "SKIP: Ollama reachable but no models found at $ollamaBaseUrl (/api/tags)"
    exit 0
}

if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found at $pythonExe. Create it first or run ./scripts/dev.ps1"
}

$port = 8001
$baseUrl = "http://127.0.0.1:$port"
$healthUrl = "$baseUrl/health"

$serverProc = $null

try {
    $env:AGENTPRESS_DATABASE_URL = 'sqlite+aiosqlite:///./.data/agentpress.auto.db'
    $env:AGENTPRESS_TOOL_CALLING_MODE = 'auto'
    $env:AGENTPRESS_LLM_PROVIDER = 'ollama'
    $env:AGENTPRESS_OLLAMA_BASE_URL = $ollamaBaseUrl
    $env:AGENTPRESS_OLLAMA_MODEL = $modelName

    $serverProc = Start-Process -FilePath $pythonExe -WorkingDirectory $backendDir -PassThru -WindowStyle Hidden -ArgumentList @(
        '-m','uvicorn','app.main:app','--port',"$port"
    )

    $health = Wait-ForHealth -Url $healthUrl -TimeoutSeconds 30
    Write-Host "OK /health (auto mode)"

    # Create an agent that will predictably do exactly one TOOL_CALL, then stop.
    function Invoke-AutoChat([string]$systemPrompt) {
        $agent = Invoke-RestMethod -Method Post -Uri "$baseUrl/agents" -ContentType 'application/json' -Body (@{
            name = 'Auto Smoke Agent'
            model = 'ollama'
            system_prompt = $systemPrompt
            temperature = 0.0
        } | ConvertTo-Json)

        Assert-True ($agent.id) 'agent create returned id'

        $msg = 'Call the echo tool and then report meta.agent_id from TOOL_RESULT. Do not guess.'
        $sse = Invoke-WebRequest -Method Post -Uri "$baseUrl/agents/$($agent.id)/chat" -ContentType 'application/json' -Body (@{
            message = $msg
        } | ConvertTo-Json) | Select-Object -ExpandProperty Content

        return @{ agentId = $agent.id; sse = $sse }
    }

    $system1 = @'
You may call tools.

Tool behavior note:
The `echo` tool returns JSON that includes `meta.agent_id` (it is provided by the server context).

Rules:
1) On the first response (before you see any TOOL_RESULT), you MUST respond with EXACTLY one line:
TOOL_CALL {"plugin_id":"echo","tool_name":"echo","params":{"text":"ping"}}
2) After you see TOOL_RESULT, respond with normal text that includes BOTH 'ok' and the value of meta.agent_id from the tool result.
'@

    $system2 = @'
CRITICAL:
The server will reject guesses.

Your entire first response MUST be exactly one line:
TOOL_CALL {"plugin_id":"echo","tool_name":"echo","params":{"text":"ping"}}

After TOOL_RESULT, reply with text containing: ok and meta.agent_id
'@

    $r = Invoke-AutoChat -systemPrompt $system1
    $agentId = $r.agentId
    $sse = $r.sse

    if (-not ($sse -match 'event: tool_call_start')) {
        Write-Host 'Retrying auto tool-call with stricter prompt...'
        $r = Invoke-AutoChat -systemPrompt $system2
        $agentId = $r.agentId
        $sse = $r.sse
    }

    $hasStart = ($sse -match 'event: tool_call_start')
    $hasEnd = ($sse -match 'event: tool_call_end')
    $hasToken = ($sse -match 'event: token')
    $hasOk = ($sse -match 'ok')
    $hasAgentId = ($sse -match [regex]::Escape($agentId))

    if (-not ($hasStart -and $hasEnd -and $hasToken -and $hasOk -and $hasAgentId)) {
        Write-Host '--- SSE transcript (debug) ---'
        Write-Host $sse
        Write-Host '------------------------------'
        Write-Host "flags: start=$hasStart end=$hasEnd token=$hasToken ok=$hasOk agentId=$hasAgentId"
    }

    Assert-True $hasStart 'auto SSE includes tool_call_start'
    Assert-True $hasEnd 'auto SSE includes tool_call_end'
    Assert-True $hasToken 'auto SSE includes token'
    Assert-True $hasOk 'final assistant text contains ok'
    Assert-True $hasAgentId 'transcript includes meta.agent_id (agent UUID)'

    Write-Host 'AUTO SMOKE PASSED'
    exit 0
}
finally {
    if ($serverProc) {
        try {
            Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
        } catch {
            # ignore
        }
    }
}
