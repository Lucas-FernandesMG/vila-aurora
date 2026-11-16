# Rede Comunitária Vila Aurora

**FIAP Global Solution 2026.2 — Segurança, IoT, Continuidade Operacional e Inteligência Artificial**

## 1. Visão geral

A Rede Comunitária Vila Aurora é uma solução de monitoramento e continuidade operacional para cinco espaços comunitários de Serra Clara (SP):

- Centro Comunitário
- Escola Municipal
- Unidade Básica de Saúde (UBS)
- Horta e Cozinha Solidária
- Abrigo de Emergência

A plataforma integra dispositivos IoT, agentes de borda, comunicação MQTT segura, API central, armazenamento local, sincronização offline e painel de supervisão.

Os eventos e sensores utilizados no laboratório são simulados.

## 2. Arquitetura

A solução está organizada em quatro camadas:

1. **Dispositivos:** 30 identidades individuais, distribuídas entre cinco espaços.
2. **Edge:** cinco agentes independentes, cada um com banco SQLite local.
3. **Central:** aplicação FastAPI, banco SQLite, autenticação, autorização e análise de eventos.
4. **Supervisão:** dashboard web para operadores.

### Tecnologias

- Python e FastAPI
- SQLite
- MQTT com Eclipse Mosquitto
- Paho MQTT
- TLS mútuo (mTLS)
- OpenSSL e autoridade certificadora própria
- WireGuard
- HTTPX
- Isolation Forest simplificado, implementado com biblioteca padrão do Python
- HTML, CSS e JavaScript

## 3. Segurança

A implementação contempla:

- Certificados X.509 individuais para os dispositivos.
- Autenticação mútua TLS no broker MQTT.
- ACLs com autorização por identidade e tópico.
- Certificados de cliente na sincronização HTTPS.
- Revogação de certificados por CRL.
- Autenticação de operadores com senha protegida por PBKDF2 e MFA TOTP.
- Controle de acesso baseado em funções (RBAC).
- Proteção de rotas administrativas.
- Consultas parametrizadas e validação de entradas.
- Captura forense com hash SHA-256.

A VPN WireGuard possui configuração e scripts de validação. A comunicação entre computadores distintos depende de teste no ambiente correspondente.

## 4. Continuidade e sincronização

Cada agente mantém suas leituras em banco SQLite local.

Quando a central fica indisponível:

- As leituras continuam sendo registradas localmente.
- Os eventos permanecem pendentes.
- A sincronização ocorre quando a central volta a responder.
- A central utiliza identificadores únicos para evitar duplicação.
- O agente marca os eventos como sincronizados somente após confirmação.

O teste de indisponibilidade de 30 minutos foi realizado simulando a indisponibilidade da API central, sem desconectar fisicamente a rede WAN.

## 5. Inteligência artificial

O módulo `central/analytics.py` implementa uma versão simplificada de detecção de anomalias baseada em árvores de isolamento, sem dependência de scikit-learn.

O módulo utiliza dados de telemetria para identificar observações atípicas.

A avaliação de precisão, recall e falsos positivos deve considerar um conjunto sintético rotulado. A implementação não substitui avaliação operacional em sensores reais.

## 6. Incidente INC-VA-0712

O cenário simula um incidente envolvendo:

- Engenharia social e phishing.
- Comprometimento de credenciais.
- Acesso remoto indevido.
- Tentativa de SQL injection.
- Alteração indevida de programação de bomba d'água.
- Interrupção de conectividade.
- Falha de alertas dependentes de nuvem.
- Necessidade de centralização e preservação de evidências.

Os eventos são sintéticos e utilizados exclusivamente para demonstração defensiva.

## 7. Estrutura do projeto

- `agent/`: agentes de borda, armazenamento local, MQTT e sincronização.
- `central/`: API, banco central, autenticação, dashboard, monitoramento e análise.
- `config/`: configurações dos agentes, broker, ACL e VPN.
- `pki/`: scripts e configuração da infraestrutura de certificados.
- `scripts/`: inicialização, testes de caos, VPN, ACL e coleta forense.
- `tests/`: testes automatizados.
- `data/`: bancos, certificados, chaves, logs e evidências locais. Não deve ser publicado no repositório.

## 8. Requisitos de ambiente

- Windows 10 ou 11.
- Python 3.15.2 (versão utilizada na validação atual).
- Mosquitto 2.x.
- OpenSSL 3.x.
- WireGuard para os testes de VPN.
- PowerShell.
- VS Code recomendado.

## 9. Instalação

Na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Se a política de execução bloquear a ativação:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 10. Configuração de autenticação

Antes de iniciar a API, defina o segredo usado para assinar os tokens de sessão.
No Git Bash:

```text
export VILA_AUTH_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

No PowerShell:

```powershell
$env:VILA_AUTH_SECRET = [Convert]::ToBase64String([byte[]](1..32 | ForEach-Object { Get-Random -Maximum 256 }))
```

O segredo deve ter pelo menos 32 caracteres e precisa ser definido no mesmo
terminal em que a API for iniciada. Ele não é o código do aplicativo
Authenticator: o Authenticator gera o código MFA de seis dígitos usado no login.

Crie o primeiro operador local antes do primeiro acesso:

```text
python scripts/create_operator.py
```

O script solicita o usuário, uma senha com pelo menos 12 caracteres e o papel
(`admin`, `operator` ou `auditor`). Ao final, cadastre o segredo TOTP exibido
no Google Authenticator, Aegis ou outro aplicativo compatível.

Os operadores são persistidos no banco SQLite local
`data/central/central.db`. Esse arquivo e a pasta `data/` são ignorados pelo
Git para evitar o compartilhamento de credenciais, hashes e segredos MFA.
Assim, cada nova instalação precisa criar seu próprio operador.

## 11. Inicialização

API central:

```powershell
python -m uvicorn central.main:app --host 127.0.0.1 --port 8000
```

Dashboard:

http://127.0.0.1:8000/dashboard

Documentação da API:

http://127.0.0.1:8000/docs

Agente individual:

```powershell
python -m agent.main --agent centro --cycles 5 --interval 1
```

Todos os agentes:

```powershell
python -m agent.main --all --cycles 5 --interval 1
```

Agente com MQTT mTLS:

```powershell
python -m agent.main --agent centro --cycles 1 --interval 1 --mqtt --mqtt-host 127.0.0.1 --mqtt-port 8883
```

Broker MQTT:

```powershell
& "C:\Program Files\Mosquitto\mosquitto.exe" -c config\mosquitto\mosquitto.conf -v
```

Execute o comando a partir da raiz do projeto, após gerar os certificados e provisionar os arquivos locais necessários.

## 12. Testes

Execute:

```powershell
python -m pytest -v
```

Última validação registrada no ambiente de desenvolvimento:

- 63 testes aprovados.
- Nenhuma falha.
- Um aviso de depreciação relacionado à integração Starlette e HTTPX.

## 13. Limitações do laboratório

- Não foram utilizados sensores físicos.
- Os dados de telemetria são simulados.
- O teste de 30 minutos simulou indisponibilidade da API central, não uma interrupção física da WAN.
- O broker MQTT está configurado para escutar em loopback no laboratório local.
- A validação da VPN entre computadores distintos depende de ambiente externo.
- Não foi realizado teste de phishing contra pessoas reais.
- Não foi utilizado LLM na solução.
- A solução não foi implantada em infraestrutura de produção.

## 14. Segurança do repositório

Não publicar:

- Chaves privadas.
- Senhas e tokens.
- Banco de dados local.
- Certificados e materiais privados da CA.
- Arquivos de configuração com segredos.
- Conteúdo da pasta `data/`.

Os arquivos sensíveis devem ser gerados localmente por meio dos scripts de provisionamento.

## 15. Estado da validação

O projeto possui testes automatizados e validações reais de componentes no laboratório local. As limitações de infraestrutura e os testes ainda pendentes devem ser considerados na avaliação final.

**Rede Comunitária Vila Aurora — FIAP Global Solution 2026.2**