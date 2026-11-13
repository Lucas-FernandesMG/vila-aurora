# VPN WireGuard ? Rede Comunit?ria Vila Aurora

## Topologia

- Central: `10.77.0.1/24`, UDP `51820`
- Segundo ponto: `10.77.0.2/32`
- Rede VPN: `10.77.0.0/24`
- Protocolo: WireGuard

## Arquivos e seguran?a

- `data/vpn/central.conf`: configura??o privada do ponto central.
- `data/vpn/segundo_ponto.conf`: configura??o privada do segundo ponto.
- `config/vpn/README.md`: este procedimento.

Os arquivos em `data/vpn` cont?m chaves privadas. N?o os envie ao GitHub.
Nunca compartilhe `central.conf`. Compartilhe `segundo_ponto.conf` somente
com o colega respons?vel pelo segundo ponto e por um canal privado.

## Prepara??o do computador central

1. Copie o projeto e mantenha `data/vpn/central.conf` no computador central.
2. Descubra o endere?o IP LAN do computador central.
3. Abra PowerShell como administrador na pasta do projeto.
4. Execute:
   `.\scripts\vpn_smoke.ps1 -InstallCentral`
5. Se os computadores estiverem em redes diferentes, ser? necess?rio configurar
   encaminhamento UDP 51820 no roteador e usar o IP p?blico ou DNS do central.
   N?o exponha servi?os administrativos diretamente ? internet.

## Prepara??o do segundo computador

1. Instale o aplicativo oficial WireGuard para Windows.
2. Receba somente `segundo_ponto.conf` por canal privado.
3. Coloque-o em `data\vpn\segundo_ponto.conf` no projeto ou importe-o
   diretamente no aplicativo WireGuard.
4. No PowerShell, execute:
   `.\scripts\vpn_smoke.ps1 -EndpointAddress "IP_LAN_DO_CENTRAL"`
5. Importe a configura??o atualizada no WireGuard e ative o t?nel.

## Teste de integra??o

Com o t?nel ativo no segundo computador, execute:
`.\scripts\vpn_smoke.ps1 -Check`

O teste exige handshake recente e resposta do endere?o VPN central `10.77.0.1`.
Se o ping for bloqueado pela pol?tica de firewall, o handshake ainda comprova
a negocia??o criptogr?fica, mas a conectividade IP precisa ser testada por
outro servi?o permitido na rede VPN.

## Limita??es da valida??o local

A gera??o das chaves e a consist?ncia das configura??es podem ser testadas
neste computador. A comunica??o entre dois pares independentes depende de
um segundo computador e ainda precisa de evid?ncia de execu??o.

N?o declarar o t?nel como funcional antes do handshake e do teste de tr?fego.
