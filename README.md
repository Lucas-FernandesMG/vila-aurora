# Rede Comunitária Vila Aurora — Etapas 0 e 1

Base funcional: banco central SQLite, cinco agentes independentes (simulados) e API FastAPI.
Etapas futuras (MQTT, sincronização, PKI, VPN) **não** estão implementadas.

## Requisitos
- Windows, Python 3.10+ (testado no código com 3.12), VS Code, 8 GB de RAM.
- Dependências: `fastapi`, `uvicorn`, `pyyaml`, `pytest`, `httpx` (ver `requirements.txt`).

## Preparação do ambiente (PowerShell, na pasta `vila-aurora`)
```powershell
python --version
python -m pip --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -c "import fastapi, pytest, yaml; print('ok')"
```
Se a ativação for bloqueada por política de execução, use sem privilégio de administrador:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` ou chame `.\.venv\Scripts\python.exe` diretamente.

## Executar
API (cria `data/central/central.db` automaticamente):
```powershell
python -m uvicorn central.main:app --reload
```
- API: http://127.0.0.1:8000 — documentação: http://127.0.0.1:8000/docs

Agentes (cada um grava em `data/agents/<id>/local.db`):
```powershell
python -m agent.main --agent centro --cycles 5 --interval 1   # um agente
python -m agent.main --all --cycles 5 --interval 1            # os cinco, em um processo
```
API + agentes de uma vez (Ctrl+C encerra ambos): `.\scripts\run_all.ps1`

## Testes
```powershell
python -m pytest -v
```
Os testes usam bancos em diretórios temporários e não alteram `data/`.

## Endpoints
`GET /health`, `/api/spaces`, `/api/spaces/{space_id}`, `/api/devices`, `/api/telemetry`, `/api/alerts`, `/api/status`.
Filtros: `space_id`, `device_id`, `metric`, `severity`, `resolved`, `limit` (1–1000), `offset`.
Nesta etapa os agentes ainda não enviam dados ao central, então telemetria e alertas começam vazios.

> Status de validação: no ambiente de desenvolvimento (sem acesso à internet) foram executados
> apenas os agentes (`python -m agent.main`), o banco central e a lógica de consulta. A instalação via pip,
> `uvicorn`, `pytest` (incluindo `tests/test_api.py`) e `scripts/run_all.ps1` **ainda precisam ser executados**
> na máquina Windows do projeto.
