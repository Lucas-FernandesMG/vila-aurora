$ErrorActionPreference = "Stop"

$wg = "C:\Program Files\WireGuard\wg.exe"
if (-not (Test-Path $wg)) {
    throw "WireGuard não encontrado em: $wg"
}

New-Item -ItemType Directory -Force -Path ".\config\vpn", ".\data\vpn" | Out-Null

$serverPrivate = (& $wg genkey).Trim()
$serverPublic = ($serverPrivate | & $wg pubkey).Trim()

$clientPrivate = (& $wg genkey).Trim()
$clientPublic = ($clientPrivate | & $wg pubkey).Trim()

@"
[Interface]
PrivateKey = $serverPrivate
Address = 10.77.0.1/24
ListenPort = 51820

[Peer]
PublicKey = $clientPublic
AllowedIPs = 10.77.0.2/32
"@ | Set-Content ".\data\vpn\central.conf" -Encoding ascii

@"
[Interface]
PrivateKey = $clientPrivate
Address = 10.77.0.2/32

[Peer]
PublicKey = $serverPublic
Endpoint = IP_DO_COMPUTADOR_CENTRAL:51820
AllowedIPs = 10.77.0.0/24
PersistentKeepalive = 25
"@ | Set-Content ".\data\vpn\segundo_ponto.conf" -Encoding ascii

@"
Chaves e configurações WireGuard geradas.
Central: 10.77.0.1/24
Segundo ponto: 10.77.0.2/32
Porta UDP: 51820
Substituir IP_DO_COMPUTADOR_CENTRAL pelo IP LAN do computador central antes da conexão.
"@ | Set-Content ".\config\vpn\README.txt" -Encoding ascii

Write-Host "Configuracoes WireGuard geradas."
Write-Host "Arquivos privados: data\vpn\"
Write-Host "Nao compartilhe nem versione as chaves privadas."
