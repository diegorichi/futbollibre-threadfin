$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Falta Docker Desktop y winget. Instalá Docker Desktop desde https://www.docker.com/products/docker-desktop/"
    }
    winget install --id Docker.DockerDesktop --exact --accept-package-agreements --accept-source-agreements
}

$DockerDesktop = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
if (Test-Path $DockerDesktop) { Start-Process $DockerDesktop }

Write-Host "Esperando a Docker Desktop..."
for ($i = 0; $i -lt 60; $i++) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop no inició." }

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
docker compose up --build -d
Start-Process "http://localhost:8080"
