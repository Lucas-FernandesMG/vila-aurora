# VPN WireGuard — Rede Comunit?ria Vila Aurora

## Topologia

- Central: `10.77.0.1/24`, UDP `51820`
- Segundo ponto: `10.77.0.2/32`
- Rede VPN: `10.77.0.0/24`
- Protocolo: WireGuard

## Arquivos e segurança

- `data/vpn/central.conf`: configuração privada do ponto central.
- `data/vpn/segundo_ponto.conf`: configuração privada do segundo ponto.
- `config/vpn/README.md`: este procedimento.

Os arquivos em `data/vpn` contêm chaves privadas. N?o os envie ao GitHub.
Nunca compartilhe `central.conf`. Compartilhe `segundo_ponto.conf` somente
com o colega respons?vel pelo segundo ponto e por um canal privado.

## Preparação do computador central

1. Copie o projeto e mantenha `data/vpn/central.conf` no computador central.
2. Descubra o endereço IP LAN do computador central.
3. Abra PowerShell como administrador na pasta do projeto.
4. Execute:
   `.\scripts\vpn_smoke.ps1 -InstallCentral`
5. Se os computadores estiverem em redes diferentes, será necess?rio configurar
   encaminhamento UDP 51820 no roteador e usar o IP p?blico ou DNS do central.
   N?o exponha servi?os administrativos diretamente à internet.

## Preparação do segundo computador

1. Instale o aplicativo oficial WireGuard para Windows.
2. Receba somente `segundo_ponto.conf` por canal privado.
3. Coloque-o em `data\vpn\segundo_ponto.conf` no projeto ou importe-o
   diretamente no aplicativo WireGuard.
4. No PowerShell, execute:
   `.\scripts\vpn_smoke.ps1 -EndpointAddress "IP_LAN_DO_CENTRAL"`
5. Importe a configuração atualizada no WireGuard e ative o t?nel.

## Teste de integração

Com o t?nel ativo no segundo computador, execute:
`.\scripts\vpn_smoke.ps1 -Check`

O teste exige handshake recente e resposta do endereço VPN central `10.77.0.1`.
Se o ping for bloqueado pela pol?tica de firewall, o handshake ainda comprova
a negociação criptográfica, mas a conectividade IP precisa ser testada por
outro servi?o permitido na rede VPN.

## Limitações da validação local

A geração das chaves e a consistência das configurações podem ser testadas
neste computador. A comunicação entre dois pares independentes depende de
um segundo computador e ainda precisa de evid?ncia de execução.

N?o declarar o t?nel como funcional antes do handshake e do teste de tr?fego.
