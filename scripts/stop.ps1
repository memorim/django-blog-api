$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$stopped = $false

if (Get-Command docker -ErrorAction SilentlyContinue) {
    & docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        & docker compose down
        if ($LASTEXITCODE -ne 0) {
            throw "Docker Compose could not stop the project."
        }
        $stopped = $true
    }
}

$pidPath = Join-Path $projectRoot ".local-server.pid"
if (Test-Path -LiteralPath $pidPath) {
    $serverProcessId = 0
    $rawProcessId = [IO.File]::ReadAllText($pidPath).Trim()
    if ([int]::TryParse($rawProcessId, [ref]$serverProcessId)) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $serverProcessId" -ErrorAction SilentlyContinue
        if ($process -and $process.CommandLine -match "manage\.py\s+runserver") {
            Stop-Process -Id $serverProcessId
            $stopped = $true
        }
    }
    Remove-Item -LiteralPath $pidPath
}

if ($stopped) {
    Write-Host "The project has been stopped."
}
else {
    Write-Host "The project was not running."
}
