# FlowDesk Lab API

## Contexto

API pedagógica para a disciplina FIAP de Tools, Automations and Workflows.
Representa uma central inteligente de solicitações internas (FlowDesk Lab).

O objetivo é permitir que alunos explorem:
- REST APIs (GET/POST)
- Path parameters, headers, JSON
- Webhooks, HTTP Request
- Mapping, routing
- LLM workflows, structured output, tool calling
- Error handling, timeout, retry, rate limiting
- Human-in-the-Loop
- Observabilidade
- Contratos OpenAPI

## Arquitetura

```text
LLM / Agent
    ↓
Workflow (n8n / Make / Dify)
    ↓
FlowDesk API
    ↓
Data / Ticket System
```

## Requisitos

- Python 3.12
- pip

## Instalação

### Criar venv

**Mac/Linux:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

**Windows:**

```bash
python3.12 -m venv .venv
.venv\Scripts\activate
```

### Instalar dependências

```bash
cd api
pip install -r requirements.txt
```

Para desenvolvimento (com testes):

```bash
pip install -r requirements-dev.txt
```

## Executar

```bash
cd api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Swagger

Acesse: http://localhost:8000/docs

## OpenAPI

Acesse: http://localhost:8000/openapi.json

> Para integrações com Dify, n8n, Make e agentes, valide na instância em execução se o contrato publicado em `/openapi.json` expõe as operações esperadas antes de importar ou automatizar.

## Testar

```bash
cd api
pytest -v
```

## Docker

```bash
cd api
docker build -t flowdesk-lab-api .
docker run -p 8000:8000 flowdesk-lab-api
```

## Deploy

- Railway: veja [RAILWAY_DEPLOY.md](./RAILWAY_DEPLOY.md)
- GitHub: veja [GITHUB_SETUP.md](./GITHUB_SETUP.md)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root endpoint |
| GET | `/health` | Health check |
| GET | `/api/v1/employees/{employee_id}` | Get employee |
| GET | `/api/v1/teams/{category}` | Get team |
| POST | `/api/v1/priority/check` | Check priority |
| POST | `/api/v1/tickets` | Create ticket |
| GET | `/api/v1/tickets/{ticket_id}` | Get ticket |
| GET | `/api/v1/tickets` | List tickets |
| POST | `/api/v1/access-requests` | Create access request |
| GET | `/api/v1/access-requests/{request_id}` | Get access request |
| POST | `/api/v1/access-requests/{request_id}/approve` | Approve/reject request |
| GET | `/api/v1/events` | List audit events |
| GET | `/api/v1/lab/slow` | Simulated slow response |
| GET | `/api/v1/lab/error` | Simulated 500 error |
| GET | `/api/v1/lab/rate-limit` | Rate limit demo |
| GET | `/api/v1/lab/not-found` | Simulated 404 |
| POST | `/api/v1/lab/validation` | Validation error demo |

## X-Student-ID

Os endpoints de negócio e laboratório em `/api/v1/*` aceitam o header `X-Student-ID` para contexto de execução do laboratório.
Nos fluxos que criam registros, esse valor é persistido em `student_id`.
Esse header é um mecanismo didático de particionamento de contexto, não autenticação.

```bash
curl -H "X-Student-ID: grupo-07" http://localhost:8000/api/v1/tickets
```

Se não enviado, o valor padrão é `anonymous`.

## Exemplos de Requests

Use os exemplos descritos em `API_CONTRACTS.md`, `N8N_LAB.md`, `MAKE_LAB.md` e `DIFY_LAB.md`.

## Observação sobre contrato e instância executada

Os contratos desta pasta foram escritos a partir dos handlers e modelos presentes em `api/app/`.
Antes de uma aula, deploy ou importação como tool, confirme na instância ativa se `/docs` e `/openapi.json` estão refletindo essas operações.

## Casos Didáticos de Erro

| Endpoint | Erro | Uso |
|----------|------|-----|
| `/api/v1/lab/slow?seconds=10` | Timeout | Retry, fallback |
| `/api/v1/lab/error` | 500 | Error handling |
| `/api/v1/lab/rate-limit` | 429 | Rate limit |
| `/api/v1/lab/not-found` | 404 | Not found handling |
| `/api/v1/lab/validation` | 422 | Validation |

## Documentação complementar

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [API_CONTRACTS.md](./API_CONTRACTS.md)
- [CLASSROOM_SCENARIOS.md](./CLASSROOM_SCENARIOS.md)
- [N8N_LAB.md](./N8N_LAB.md)
- [MAKE_LAB.md](./MAKE_LAB.md)
- [DIFY_LAB.md](./DIFY_LAB.md)
