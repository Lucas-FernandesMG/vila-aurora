<#
Inicia a API central e os cinco agentes (em um único processo de agentes).
Uso (na raiz do projeto ou de qualquer pasta):  .\scripts\run_all.ps1
Parâmetros opcionais: -Port 8000 -Interval 5
Pressione Ctrl+C para encerrar tudo. Não exige privilégios de administrador.
#>
param(
    [int]$Port = 8000,
    [double]$Interval = 5
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Ambiente virtual não encontrado. Execute: python -m venv .venv ; .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

Write-Host "API: http://127.0.0.1:$Port  (docs: http://127.0.0.1:$Port/docs)"
$api = Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "central.main:app", "--host", "127.0.0.1", "--port", "$Port") `
    -NoNewWindow -PassThru

try {
    & $python -m agent.main --all --interval $Interval
}
finally {
    if ($api -and -not $api.HasExited) {
        Stop-Process -Id $api.Id -Force
    }
}
