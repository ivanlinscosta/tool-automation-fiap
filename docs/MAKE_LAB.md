# FlowDesk Lab com Make

## Visão geral

Este guia mostra como reproduzir no Make os principais padrões trabalhados com a FlowDesk Lab API:

- entrada via webhook
- chamadas HTTP
- branching com Router
- filtros
- parsing JSON
- criação de ticket

Base URL usada nos exemplos:

```text
http://localhost:8000
```

> Antes de construir o cenário, valide em `/docs` e `/openapi.json` se a instância ativa está expondo os endpoints esperados pelo laboratório.

Header didático sugerido:

```text
X-Student-ID: grupo-07
```

## Cenário 1 — Explorer simples

### Módulos

```text
Custom Webhook → HTTP Make a request → Webhook response
```

### 1. Custom Webhook

Recebe um payload como:

```json
{
  "employee_id": "EMP001"
}
```

### 2. HTTP - Make a request

- **Method:** `GET`
- **URL:** `http://localhost:8000/api/v1/employees/{{1.employee_id}}`
- **Headers:**

```text
X-Student-ID: grupo-07
X-Request-ID: make-explorer-001
```

### 3. Webhook response

Retorne o JSON do módulo HTTP diretamente ou monte uma resposta menor com os campos necessários.

## Cenário 2 — Triage com roteamento

### Módulos

```text
Custom Webhook → HTTP Get Employee → AI/LLM step → Parse JSON → HTTP Check Priority → Router → HTTP Get Team → HTTP Create Ticket → Webhook response
```

### Passos principais

#### A. HTTP Get Employee

```text
GET http://localhost:8000/api/v1/employees/{{1.employee_id}}
```

#### B. AI/LLM step

Peça ao modelo um JSON com:

```json
{
  "category": "it|hr|finance|facilities|security|other",
  "impact": "low|medium|high",
  "urgency": "low|medium|high",
  "summary": "...",
  "description": "..."
}
```

#### C. Parse JSON

Use um módulo de parse/transform para validar o JSON retornado pelo LLM antes da chamada à API.

#### D. HTTP Check Priority

- **Method:** `POST`
- **URL:** `http://localhost:8000/api/v1/priority/check`
- **Headers:** `Content-Type: application/json`, `X-Student-ID: grupo-07`
- **Body:**

```json
{
  "employee_id": "{{1.employee_id}}",
  "category": "{{parse.category}}",
  "impact": "{{parse.impact}}",
  "urgency": "{{parse.urgency}}"
}
```

#### E. Router

Crie ramos para `it`, `hr`, `finance`, `facilities`, `security` e `other`.

#### F. Filters

Em cada ramo, aplique filtros como:

```text
category = it
category = hr
category = security
```

#### G. HTTP Get Team

```text
GET http://localhost:8000/api/v1/teams/{{parse.category}}
```

#### H. HTTP Create Ticket

- **Method:** `POST`
- **URL:** `http://localhost:8000/api/v1/tickets`
- **Body:**

```json
{
  "employee_id": "{{1.employee_id}}",
  "category": "{{parse.category}}",
  "impact": "{{parse.impact}}",
  "urgency": "{{parse.urgency}}",
  "summary": "{{parse.summary}}",
  "description": "{{parse.description}}",
  "source": "make"
}
```

## Cenário 3 — Tratamento de erro

### Endpoints didáticos

- `/api/v1/lab/slow?seconds=10`
- `/api/v1/lab/error`
- `/api/v1/lab/rate-limit`

### Estratégias no Make

- use timeout curto no módulo HTTP
- crie rotas de erro para fallback
- registre retries em variáveis ou logs do cenário
- respeite o header `Retry-After` em exercícios de 429

## Cenário 4 — Human-in-the-Loop

### Fluxo sugerido

```text
Webhook → LLM Risk Assessment → HTTP Create Access Request → Router/Filter → aprovação humana → HTTP Approve Access Request
```

### Regras da API

- `risk = low` → `auto_approved`
- `risk = medium` ou `high` → `pending_approval`

### Body de criação

```json
{
  "employee_id": "EMP006",
  "resource": "Security Admin Console",
  "justification": "Investigação de alertas e suporte operacional.",
  "risk": "high"
}
```

### Body de aprovação

```json
{
  "approved_by": "manager@flowdesk.lab",
  "decision": "approved",
  "decision_comment": "Approved after classroom review."
}
```

## Comparação rápida: Make vs n8n

| Tema | n8n | Make |
|------|-----|------|
| Entrada HTTP | Webhook node | Custom Webhook module |
| API call | HTTP Request | HTTP - Make a request |
| Branching | Switch / IF | Router + Filters |
| Manipulação de dados | Expressions e Set/Code | Mapping visual e módulos de parse |
| Erros | Error Trigger, retries por node | Error handlers e rotas de erro do cenário |
| Estilo | canvas com nodes | cenário orientado a módulos |

## Quando usar cada abordagem em aula

- **n8n:** ótimo para visualizar o fluxo completo e demonstrar expressões
- **Make:** ótimo para mostrar roteamento modular e filtros por ramo

## Dicas

- fixe `X-Student-ID` por equipe
- use `source: "make"` ao abrir tickets
- comece com Explorer simples antes do triage com LLM
