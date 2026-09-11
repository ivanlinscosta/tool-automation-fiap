# API Contracts

## Convenções gerais

### Base URL

```text
http://localhost:8000
```

> Antes de integrar a API em ferramentas externas, confira se a instância ativa publica o contrato esperado em `/openapi.json`.

### Headers comuns

| Header | Obrigatório | Observação |
|--------|-------------|------------|
| `Content-Type: application/json` | apenas em `POST` com body JSON | padrão para requests com payload |
| `X-Student-ID` | opcional | default `anonymous`; usado como contexto didático |
| `X-Request-ID` | opcional | útil para rastreabilidade em workflows |

`X-Student-ID` não é um mecanismo de autenticação.

### Categorias válidas

```text
it, hr, finance, facilities, security, other
```

### Valores válidos de impact e urgency

```text
low, medium, high
```

---

## GET `/`

### Purpose

Retorna links básicos do serviço.

### Request headers

Nenhum obrigatório.

### Response example

```json
{
  "service": "FlowDesk Lab API",
  "docs": "/docs",
  "openapi": "/openapi.json",
  "health": "/health"
}
```

### Error responses

Não há erros específicos documentados além de falhas gerais de servidor.

### curl

```bash
curl http://localhost:8000/
```

---

## GET `/health`

### Purpose

Health check da aplicação.

### Response example

```json
{
  "status": "ok",
  "service": "flowdesk-lab-api",
  "version": "1.0.0"
}
```

### Error responses

Não há erros específicos documentados além de falhas gerais de servidor.

### curl

```bash
curl http://localhost:8000/health
```

---

## GET `/api/v1/employees/{employee_id}`

### Purpose

Busca um funcionário pelo identificador.

### Request headers

- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Path params

| Param | Type | Example |
|-------|------|---------|
| `employee_id` | string | `EMP001` |

### Response schema

```json
{
  "id": "EMP001",
  "name": "Ayla Mercer",
  "department": "Marketing",
  "email": "ayla.mercer@example.com",
  "role": "Analista",
  "vip": false
}
```

### Error responses

#### 404

```json
{
  "detail": "Employee not found"
}
```

### curl

```bash
curl -H "X-Student-ID: grupo-07" \
  http://localhost:8000/api/v1/employees/EMP001
```

---

## GET `/api/v1/teams/{category}`

### Purpose

Retorna o time responsável por uma categoria.

### Request headers

- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Path params

| Param | Type | Example |
|-------|------|---------|
| `category` | string | `it` |

### Response schema

```json
{
  "category": "it",
  "team_name": "IT Support",
  "email": "it@example.com",
  "queue": "technical-support",
  "sla_default_hours": 4
}
```

### Error responses

#### 404

```json
{
  "detail": "Team not found for category: unknown"
}
```

### curl

```bash
curl -H "X-Student-ID: grupo-07" \
  http://localhost:8000/api/v1/teams/it
```

---

## POST `/api/v1/priority/check`

### Purpose

Calcula prioridade de forma determinística a partir de `category`, `impact` e `urgency`.

### Request headers

- `Content-Type: application/json`
- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Body schema

```json
{
  "employee_id": "EMP001",
  "category": "it",
  "impact": "medium",
  "urgency": "high"
}
```

### Response schema

```json
{
  "priority": "high",
  "sla_hours": 4,
  "requires_escalation": true,
  "rule": "medium_high_impact_urgency"
}
```

### Error responses

#### 422

Exemplo quando `impact` ou `urgency` estão fora do enum:

```json
{
  "detail": [
    {
      "loc": ["body", "impact"],
      "msg": "Input should be 'low', 'medium' or 'high'",
      "type": "literal_error"
    }
  ]
}
```

### curl

```bash
curl -X POST http://localhost:8000/api/v1/priority/check \
  -H "Content-Type: application/json" \
  -H "X-Student-ID: grupo-07" \
  -d '{"employee_id":"EMP001","category":"it","impact":"medium","urgency":"high"}'
```

---

## POST `/api/v1/tickets`

### Purpose

Cria um ticket e atribui o time automaticamente com base na categoria.

### Request headers

- `Content-Type: application/json`
- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Body schema

```json
{
  "employee_id": "EMP001",
  "category": "it",
  "impact": "medium",
  "urgency": "high",
  "summary": "Falha de acesso à VPN",
  "description": "Funcionário não consegue acessar a VPN e precisa continuar o trabalho hoje.",
  "source": "api"
}
```

### Response schema

```json
{
  "ticket_id": "TK-1001",
  "status": "open",
  "employee_id": "EMP001",
  "category": "it",
  "priority": "high",
  "assigned_team": "IT Support",
  "queue": "technical-support",
  "summary": "Falha de acesso à VPN",
  "description": "Funcionário não consegue acessar a VPN e precisa continuar o trabalho hoje.",
  "source": "api",
  "student_id": "grupo-07",
  "created_at": "2026-09-11T10:00:00Z",
  "updated_at": null
}
```

### Error responses

#### 422

Exemplo por campo ausente:

```json
{
  "detail": [
    {
      "loc": ["body", "summary"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

### curl

```bash
curl -X POST http://localhost:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -H "X-Student-ID: grupo-07" \
  -d '{"employee_id":"EMP001","category":"it","impact":"medium","urgency":"high","summary":"Falha de acesso à VPN","description":"Funcionário não consegue acessar a VPN e precisa continuar o trabalho hoje.","source":"api"}'
```

---

## GET `/api/v1/tickets/{ticket_id}`

### Purpose

Busca um ticket pelo identificador.

### Request headers

- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Observação de escopo

Na prática de laboratório, esse header pode alterar o conjunto de registros retornados por algumas listagens.

### Path params

| Param | Type | Example |
|-------|------|---------|
| `ticket_id` | string | `TK-1001` |

### Response schema

Mesmo schema da criação de ticket.

### Error responses

#### 404

```json
{
  "detail": "Ticket not found"
}
```

### curl

```bash
curl -H "X-Student-ID: grupo-07" \
  http://localhost:8000/api/v1/tickets/TK-1001
```

---

## GET `/api/v1/tickets`

### Purpose

Lista tickets com filtros opcionais.

### Request headers

- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Query params

| Param | Type | Example | Observação |
|-------|------|---------|------------|
| `employee_id` | string | `EMP001` | filtro opcional |
| `category` | string | `it` | filtro opcional |
| `priority` | string | `high` | filtro opcional |
| `status` | string | `open` | filtro opcional |

### Response schema

```json
[
  {
    "ticket_id": "TK-1001",
    "status": "open",
    "employee_id": "EMP001",
    "category": "it",
    "priority": "high",
    "assigned_team": "IT Support",
    "queue": "technical-support",
    "summary": "Falha de acesso à VPN",
    "description": "Funcionário não consegue acessar a VPN e precisa continuar o trabalho hoje.",
    "source": "n8n",
    "student_id": "grupo-07",
    "created_at": "2026-09-11T10:00:00Z",
    "updated_at": null
  }
]
```

### Error responses

Sem erros específicos além de falhas gerais de servidor.

### curl

```bash
curl -H "X-Student-ID: grupo-07" \
  "http://localhost:8000/api/v1/tickets?employee_id=EMP001&category=it&priority=high&status=open"
```

---

## POST `/api/v1/access-requests`

### Purpose

Cria uma solicitação de acesso com política didática de autoaprovação para risco `low`.

### Request headers

- `Content-Type: application/json`
- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Body schema

```json
{
  "employee_id": "EMP006",
  "resource": "Security Admin Console",
  "justification": "Necessário para investigação de alertas operacionais.",
  "risk": "high"
}
```

### Response schema

```json
{
  "request_id": "AR-501",
  "employee_id": "EMP006",
  "resource": "Security Admin Console",
  "justification": "Necessário para investigação de alertas operacionais.",
  "risk": "high",
  "status": "pending_approval",
  "requires_human_approval": true,
  "approved_by": null,
  "decision": null,
  "decision_comment": null,
  "decision_at": null,
  "student_id": "grupo-07",
  "created_at": "2026-09-11T10:00:00Z"
}
```

### Error responses

#### 422

Exemplo com `risk` inválido:

```json
{
  "detail": [
    {
      "loc": ["body", "risk"],
      "msg": "Input should be 'low', 'medium' or 'high'",
      "type": "literal_error"
    }
  ]
}
```

### curl

```bash
curl -X POST http://localhost:8000/api/v1/access-requests \
  -H "Content-Type: application/json" \
  -H "X-Student-ID: grupo-07" \
  -d '{"employee_id":"EMP006","resource":"Security Admin Console","justification":"Necessário para investigação de alertas operacionais.","risk":"high"}'
```

---

## GET `/api/v1/access-requests/{request_id}`

### Purpose

Consulta uma solicitação de acesso pelo identificador.

### Request headers

- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Path params

| Param | Type | Example |
|-------|------|---------|
| `request_id` | string | `AR-501` |

### Response schema

Mesmo schema da criação da solicitação de acesso.

### Error responses

#### 404

```json
{
  "detail": "Access request not found"
}
```

#### Observação comportamental

O fluxo de aprovação pressupõe que a solicitação esteja em `pending_approval`.
Se a instância em execução não tratar esse caso explicitamente, reaprovar um item já decidido pode resultar em erro de aplicação.

### curl

```bash
curl -H "X-Student-ID: grupo-07" \
  http://localhost:8000/api/v1/access-requests/AR-501
```

---

## POST `/api/v1/access-requests/{request_id}/approve`

### Purpose

Aprova ou rejeita uma solicitação pendente.

### Request headers

- `Content-Type: application/json`
- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Path params

| Param | Type | Example |
|-------|------|---------|
| `request_id` | string | `AR-501` |

### Body schema

```json
{
  "approved_by": "manager@flowdesk.lab",
  "decision": "approved",
  "decision_comment": "Approved after human review."
}
```

### Response schema

```json
{
  "request_id": "AR-501",
  "employee_id": "EMP006",
  "resource": "Security Admin Console",
  "justification": "Necessário para investigação de alertas operacionais.",
  "risk": "high",
  "status": "approved",
  "requires_human_approval": true,
  "approved_by": "manager@flowdesk.lab",
  "decision": "approved",
  "decision_comment": "Approved after human review.",
  "decision_at": "2026-09-11T10:15:00Z",
  "student_id": "grupo-07",
  "created_at": "2026-09-11T10:00:00Z"
}
```

### Error responses

#### 404

```json
{
  "detail": "Access request not found"
}
```

#### 422

Exemplo com decisão inválida:

```json
{
  "detail": [
    {
      "loc": ["body", "decision"],
      "msg": "Input should be 'approved' or 'rejected'",
      "type": "literal_error"
    }
  ]
}
```

### curl

```bash
curl -X POST http://localhost:8000/api/v1/access-requests/AR-501/approve \
  -H "Content-Type: application/json" \
  -H "X-Student-ID: grupo-07" \
  -d '{"approved_by":"manager@flowdesk.lab","decision":"approved","decision_comment":"Approved after human review."}'
```

---

## GET `/api/v1/events`

### Purpose

Lista eventos de auditoria.

### Request headers

- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Query params

| Param | Type | Example | Observação |
|-------|------|---------|------------|
| `event_type` | string | `ticket_created` | parâmetro aceito pela rota para uso didático |

### Observação de escopo

Essa listagem pode ser filtrada pelo contexto associado a `X-Student-ID`.

### Response schema

```json
[
  {
    "event_id": "EV-A1B2C3D4E5F6",
    "event_type": "ticket_created",
    "student_id": "grupo-07",
    "timestamp": "2026-09-11T10:00:00Z",
    "resource_type": "ticket",
    "resource_id": "TK-1001",
    "metadata_json": "{\"category\":\"it\",\"priority\":\"high\"}"
  }
]
```

> O exemplo acima representa o formato do evento. A existência de registros depende da instância executada e do fluxo que estiver populando auditoria.

### Error responses

Sem erros específicos além de falhas gerais de servidor.

### curl

```bash
curl -H "X-Student-ID: grupo-07" \
  "http://localhost:8000/api/v1/events?event_type=ticket_created"
```

---

## GET `/api/v1/lab/slow`

### Purpose

Simula resposta lenta.

### Query params

| Param | Type | Default | Regras |
|-------|------|---------|--------|
| `seconds` | integer | `5` | mínimo `1`, máximo `15` |

### Response example

```json
{
  "message": "Response after 10 seconds",
  "seconds": 10
}
```

### Error responses

#### 422

Exemplo com valor fora do range:

```json
{
  "detail": [
    {
      "loc": ["query", "seconds"],
      "msg": "Input should be less than or equal to 15",
      "type": "less_than_equal"
    }
  ]
}
```

### curl

```bash
curl -H "X-Student-ID: grupo-07" \
  "http://localhost:8000/api/v1/lab/slow?seconds=10"
```

---

## GET `/api/v1/lab/error`

### Purpose

Simula erro interno 500.

### Response error example

```json
{
  "detail": "Simulated internal server error"
}
```

### curl

```bash
curl -i -H "X-Student-ID: grupo-07" \
  http://localhost:8000/api/v1/lab/error
```

---

## GET `/api/v1/lab/rate-limit`

### Purpose

Simula rate limit por `X-Student-ID` em janela de 60 segundos.

### Regra didática

- até 3 requests por janela: `200`
- a partir da 4ª: `429`
- header `Retry-After: 10`

### Success response example

```json
{
  "message": "Request accepted",
  "student_id": "grupo-07",
  "requests_in_window": 2
}
```

### Error response example

```json
{
  "detail": "Too many requests",
  "retry_after_seconds": 10
}
```

### curl

```bash
curl -i -H "X-Student-ID: grupo-07" \
  http://localhost:8000/api/v1/lab/rate-limit
```

---

## GET `/api/v1/lab/not-found`

### Purpose

Simula um `404` didático.

### Error response example

```json
{
  "detail": "Resource not found (simulated)"
}
```

### curl

```bash
curl -i -H "X-Student-ID: grupo-07" \
  http://localhost:8000/api/v1/lab/not-found
```

---

## POST `/api/v1/lab/validation`

### Purpose

Valida `email` e `amount`, produzindo `422` quando o payload é inválido.

### Request headers

- `Content-Type: application/json`
- `X-Student-ID` (opcional)
- `X-Request-ID` (opcional)

### Body schema

```json
{
  "email": "student@flowdesk.lab",
  "amount": 42.5
}
```

### Success response example

```json
{
  "message": "Validation passed",
  "email": "student@flowdesk.lab",
  "amount": 42.5
}
```

### Error responses

#### 422

Exemplo com email inválido e amount negativo:

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error"
    },
    {
      "loc": ["body", "amount"],
      "msg": "Input should be greater than or equal to 0",
      "type": "greater_than_equal"
    }
  ]
}
```

### curl

```bash
curl -X POST http://localhost:8000/api/v1/lab/validation \
  -H "Content-Type: application/json" \
  -H "X-Student-ID: grupo-07" \
  -d '{"email":"bad-email","amount":-1}'
```

---

## Regras de prioridade usadas pela API

### Matriz padrão

| Impact | Urgency | Priority | SLA |
|--------|---------|----------|-----|
| low | low | low | 24h |
| low | medium | low | 12h |
| low | high | medium | 8h |
| medium | low | low | 12h |
| medium | medium | medium | 6h |
| medium | high | high | 4h |
| high | low | medium | 8h |
| high | medium | high | 2h |
| high | high | critical | 1h |

### Override para `security`

| Category | Urgency | Priority | SLA |
|----------|---------|----------|-----|
| security | low | high | 4h |
| security | medium | high | 2h |
| security | high | critical | 1h |
