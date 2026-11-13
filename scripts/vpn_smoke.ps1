param(
    [string]$EndpointAddress,
    [switch]$InstallCentral,
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Wg = "C:\Program Files\WireGuard\wg.exe"
$WireGuardApp = "C:\Program Files\WireGuard\wireguard.exe"
$CentralConfig = Join-Path $Root "data\vpn\central.conf"
$ClientConfig = Join-Path $Root "data\vpn\segundo_ponto.conf"

if (-not (Test-Path $Wg)) {
    throw "WireGuard wg.exe n?o encontrado."
}

if ($EndpointAddress) {
    if ($EndpointAddress -match '[:/\s]' -or $EndpointAddress -eq "IP_DO_COMPUTADOR_CENTRAL") {
        throw "Informe somente um endere?o IPv4 ou nome DNS, sem porta."
    }
    $content = Get-Content $ClientConfig -Raw
    $content = $content -replace '(?m)^Endpoint\s*=.*$', ("Endpoint = {0}:51820" -f $EndpointAddress)
    Set-Content $ClientConfig $content -Encoding ascii
    Write-Host "Endpoint do segundo ponto atualizado."
}

if ($InstallCentral) {
    $principal = New-Object Security.Principal.WindowsPrincipal(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Abra o PowerShell como administrador para instalar o t?nel central."
    }
    if (-not (Test-Path $WireGuardApp)) {
        throw "Aplicativo WireGuard n?o encontrado."
    }

    $rule = Get-NetFirewallRule -DisplayName "Vila Aurora WireGuard UDP 51820" -ErrorAction SilentlyContinue
    if (-not $rule) {
        New-NetFirewallRule `
            -DisplayName "Vila Aurora WireGuard UDP 51820" `
            -Direction Inbound -Protocol UDP -LocalPort 51820 `
            -Action Allow -Profile Private | Out-Null
    }

    & $WireGuardApp /installtunnelservice $CentralConfig
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao instalar o t?nel central. C?digo: $LASTEXITCODE"
    }
    Write-Host "Servi?o WireGuard central instalado."
}

if ($Check) {
    Write-Host "`nVerificando interfaces WireGuard..."
    $status = & $Wg show all
    $status
    if (-not $status) {
        throw "Nenhuma interface WireGuard ativa."
    }

    Write-Host "`nVerificando handshakes recentes..."
    $handshakes = & $Wg show all latest-handshakes
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $recent = $false

    foreach ($line in $handshakes) {
        $parts = $line -split '\s+'
        if ($parts.Count -ge 3) {
            $timestamp = 0L
            if ([long]::TryParse($parts[2], [ref]$timestamp) -and $timestamp -gt 0 -and ($now - $timestamp) -le 180) {
                $recent = $true
            }
        }
    }

    if (-not $recent) {
        throw "Nenhum handshake recente. Verifique endpoint, firewall e conex?o do outro ponto."
    }

    Write-Host "Handshake recente confirmado."
    Write-Host "Testando alcance do ponto central 10.77.0.1..."
    if (-not (Test-Connection -ComputerName 10.77.0.1 -Count 2 -Quiet)) {
        throw "Handshake existe, mas o ponto central n?o respondeu ao ping."
    }
    Write-Host "VPN operacional: handshake e comunica??o IP confirmados."
}

if (-not $EndpointAddress -and -not $InstallCentral -and -not $Check) {
    Write-Host "Pr?-verifica??o dos arquivos WireGuard..."
    foreach ($file in @($CentralConfig, $ClientConfig)) {
        if (-not (Test-Path $file)) { throw "Arquivo ausente: $file" }
        Write-Host "OK: $file"
    }
    Write-Host "Use -EndpointAddress para preparar o cliente."
    Write-Host "Use -InstallCentral em PowerShell elevado no computador central."
    Write-Host "Use -Check no segundo ponto depois de conectar."
}
