# API Contracts: FIAP Student Desk Lab

## Convenções Gerais

### Base URL
```text
http://localhost:8000
```

### Headers Comuns
| Header | Obrigatório | Observação |
|--------|-------------|------------|
| `Content-Type: application/json` | Sim (POST/PATCH) | Padrão para payloads JSON |
| `X-Student-ID` | Opcional | Default: `anonymous`. Usado para isolar dados entre grupos. |

---

## Endpoints de Negócio

### GET `/api/v1/students/{student_id}`
Busca dados do aluno.
**Response:**
```json
{
  "id": "STU001",
  "name": "Ivan Costa",
  "course": "Engenharia de Software",
  "status": "active"
}
```

### GET `/api/v1/knowledge/search`
Busca artigos na base de conhecimento.
**Query Params:** `q` (termo de busca), `category` (opcional).
**Response:**
```json
[
  {
    "id": "KB001",
    "title": "Acesso ao Portal",
    "content": "Para acessar o portal, use seu RM e senha...",
    "category": "digital_learning"
  }
]
```

### POST `/api/v1/priority/check`
Calcula a prioridade de uma solicitação.
**Body:**
```json
{
  "category": "digital_learning",
  "impact": "high",
  "urgency": "high"
}
```
**Response:**
```json
{
  "priority": "high",
  "sla_hours": 4
}
```

### POST `/api/v1/requests`
Cria uma nova solicitação acadêmica.
**Body:**
```json
{
  "student_id": "STU001",
  "category": "academic_services",
  "summary": "Pedido de Histórico",
  "description": "Preciso do histórico para fins de estágio."
}
```
**Response:**
```json
{
  "request_id": "REQ-123",
  "status": "open",
  "protocol": "20260911-001"
}
```

### POST `/api/v1/interactions`
Registra uma interação do assistente com o aluno.
**Body:**
```json
{
  "student_id": "STU001",
  "message": "Como acesso o portal?",
  "response": "Você deve usar seu RM...",
  "source": "n8n"
}
```

### POST `/api/v1/approval-requests/{approval_id}/decision`
Registra a decisão de um aprovador.
**Body:**
```json
{
  "decision": "approved",
  "comment": "Documento validado."
}
```

---

## Endpoints de Laboratório (Simulação de Falhas)

| Endpoint | Comportamento | Objetivo |
|----------|---------------|----------|
| `/api/v1/lab/slow` | Resposta lenta (delay) | Testar Timeout e Retry |
| `/api/v1/lab/error` | Retorna HTTP 500 | Testar Error Handling |
| `/api/v1/lab/rate-limit` | Retorna HTTP 429 após 3 chamadas | Testar Rate Limiting |
| `/api/v1/lab/not-found` | Retorna HTTP 404 | Testar tratamento de recurso ausente |
| `/api/v1/lab/validation` | Retorna HTTP 422 para dados inválidos | Testar validação de schema |

---

## Auditoria

### GET `/api/v1/events`
Lista todos os eventos registrados para o `X-Student-ID` atual. Útil para verificar se o workflow executou todos os passos esperados.
