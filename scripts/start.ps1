param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$docsUrl = "http://127.0.0.1:8000/api/docs"
Set-Location -LiteralPath $projectRoot

function Wait-ForWebApp {
    param([int]$TimeoutSeconds)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $docsUrl -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    } while ((Get-Date) -lt $deadline)

    return $false
}

function New-RandomSecret {
    $bytes = New-Object byte[] 48
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }

    return [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_").TrimEnd("=")
}

function Initialize-DockerEnvironment {
    $environmentPath = Join-Path $projectRoot ".env"
    if (Test-Path -LiteralPath $environmentPath) {
        return
    }

    $templatePath = Join-Path $projectRoot ".env.example"
    $environment = [IO.File]::ReadAllText($templatePath)
    $environment = $environment.Replace(
        "replace-with-python-secrets-token-urlsafe-output",
        (New-RandomSecret)
    ).Replace(
        "replace-with-a-long-random-password",
        (New-RandomSecret)
    )
    [IO.File]::WriteAllText(
        $environmentPath,
        $environment,
        (New-Object Text.UTF8Encoding($false))
    )
    Write-Host "Created .env with random secrets."
}

function Test-DockerReady {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return $false
    }

    & docker info *> $null
    return $LASTEXITCODE -eq 0
}

function Start-WithDocker {
    Initialize-DockerEnvironment
    Write-Host "Starting Django and PostgreSQL with Docker Compose..."
    & docker compose up --build -d
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose could not start the project."
    }
}

function Get-LocalPython {
    $venvPath = Join-Path $projectRoot ".venv"
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return $venvPython
    }

    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonLauncher) {
        & $pythonLauncher.Source -3 -m venv $venvPath
    }
    else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) {
            throw "Python 3.10+ or Docker is required."
        }
        & $python.Source -m venv $venvPath
    }

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        throw "Could not create the Python virtual environment."
    }

    return $venvPython
}

function Start-Locally {
    $python = Get-LocalPython
    & $python -c "import importlib.util; raise SystemExit(not all(importlib.util.find_spec(name) for name in ('django', 'ninja')))" 2> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing Python dependencies..."
        & $python -m pip install -r (Join-Path $projectRoot "requirements.txt")
        if ($LASTEXITCODE -ne 0) {
            throw "Could not install Python dependencies."
        }
    }

    $env:DJANGO_DEBUG = "1"
    $env:DJANGO_API_DOCS = "1"
    $env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1"
    "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT" |
        ForEach-Object { Remove-Item -LiteralPath "Env:$_" -ErrorAction SilentlyContinue }

    Write-Host "Docker is unavailable; starting the local SQLite development mode..."
    & $python manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        throw "Database migrations failed."
    }

    $stdoutPath = Join-Path $projectRoot ".local-server.out.log"
    $stderrPath = Join-Path $projectRoot ".local-server.err.log"
    $server = Start-Process `
        -FilePath $python `
        -ArgumentList @("manage.py", "runserver", "127.0.0.1:8000", "--noreload") `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru
    [IO.File]::WriteAllText((Join-Path $projectRoot ".local-server.pid"), [string]$server.Id)
}

try {
    if (Wait-ForWebApp -TimeoutSeconds 1) {
        Write-Host "The project is already running."
    }
    elseif (Test-DockerReady) {
        Start-WithDocker
    }
    else {
        Start-Locally
    }

    if (-not (Wait-ForWebApp -TimeoutSeconds 120)) {
        throw "The server did not become ready. Check Docker or .local-server.err.log."
    }

    if (-not $NoBrowser) {
        Start-Process $docsUrl
    }
    Write-Host "Ready: $docsUrl"
}
catch {
    Write-Error $_
    exit 1
}
