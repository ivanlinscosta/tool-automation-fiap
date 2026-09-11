# FlowDesk Lab com n8n

## Visão geral

Este guia descreve quatro workflows pedagógicos para consumir a FlowDesk Lab API a partir do n8n.
Os exemplos usam a API local em `http://localhost:8000` e assumem o header `X-Student-ID: grupo-07`.

> Antes de montar um workflow de aula, confira em `http://localhost:8000/docs` e `http://localhost:8000/openapi.json` se a instância ativa está publicando as operações esperadas.

> Observação: os nomes exatos de alguns nodes de IA podem variar entre versões do n8n. Os blocos abaixo usam a nomenclatura funcional mais comum: **Webhook**, **HTTP Request**, **Respond to Webhook**, **Switch**, **IF**, **Wait** e um node de **LLM/OpenAI Chat**.

## Convenções usadas nos exemplos

- Base URL: `http://localhost:8000`
- Header didático: `X-Student-ID: grupo-07`
- Employee de teste: `EMP001`
- Expressões n8n: `{{$json.body.employee_id}}`, `{{$json.category}}`, `{{$json["field"]}}`

---

## WORKFLOW 1 — API Explorer

### Objetivo

Receber um `employee_id` via webhook, consultar a API e devolver o funcionário em tempo real.

### Ordem de conexão

```text
Webhook → Get Employee → Respond to Webhook
```

### Nodes

#### 1. Node: `Webhook`
- **Type:** Webhook
- **HTTP Method:** `POST`
- **Path:** `flowdesk-api-explorer`
- **Response Mode:** `Using Respond to Webhook Node`

**Body esperado no teste:**

```json
{
  "employee_id": "EMP001"
}
```

#### 2. Node: `Get Employee`
- **Type:** HTTP Request
- **Method:** `GET`
- **URL:** `http://localhost:8000/api/v1/employees/{{$json.body.employee_id}}`
- **Send Headers:** `true`

**Headers:**

```text
X-Student-ID: grupo-07
X-Request-ID: n8n-explorer-001
```

**Resposta esperada da API:**

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

#### 3. Node: `Respond to Webhook`
- **Type:** Respond to Webhook
- **Respond With:** `JSON`

**Response Body sugerido:**

```json
{
  "employee": "={{ $json }}"
}
```

### Mapeamento de resposta

Se preferir devolver apenas alguns campos:

```json
{
  "employee_id": "={{ $json.id }}",
  "name": "={{ $json.name }}",
  "department": "={{ $json.department }}",
  "vip": "={{ $json.vip }}"
}
```

### Output esperado

```json
{
  "employee": {
    "id": "EMP001",
    "name": "Ayla Mercer",
    "department": "Marketing",
    "email": "ayla.mercer@example.com",
    "role": "Analista",
    "vip": false
  }
}
```

### Descrição de screenshot

- Canvas com três nodes em linha reta.
- `Webhook` à esquerda, `Get Employee` ao centro, `Respond to Webhook` à direita.
- Painel do `HTTP Request` mostrando URL com expressão `{{$json.body.employee_id}}`.

---

## WORKFLOW 2 — Intelligent Triage

### Objetivo

Classificar uma mensagem em linguagem natural, calcular prioridade, rotear por categoria e abrir um ticket.

### Ordem de conexão

```text
Webhook → Get Employee → LLM Classifier → Structured Output → Priority API → Switch Category → Get Team → Create Ticket → Respond to Webhook
```

### Payload de entrada sugerido

```json
{
  "employee_id": "EMP001",
  "message": "Não consigo acessar a VPN e preciso trabalhar agora para atender um incidente do cliente."
}
```

### Nodes

#### 1. Node: `Webhook`
- **Type:** Webhook
- **Method:** `POST`
- **Path:** `flowdesk-triage`
- **Response Mode:** `Using Respond to Webhook Node`

#### 2. Node: `Get Employee`
- **Type:** HTTP Request
- **Method:** `GET`
- **URL:** `http://localhost:8000/api/v1/employees/{{$json.body.employee_id}}`
- **Headers:**

```text
X-Student-ID: grupo-07
X-Request-ID: n8n-triage-employee
```

#### 3. Node: `LLM Classifier`
- **Type:** OpenAI Chat / AI Chat Model
- **Model:** configure o modelo disponível no seu ambiente
- **Input principal:** mensagem do webhook + dados do funcionário

**Prompt sugerido:**

```text
Você é um classificador de triagem do FlowDesk Lab.

Analise a solicitação abaixo e retorne SOMENTE um JSON válido.

Categorias válidas: it, hr, finance, facilities, security, other.
Impact válidos: low, medium, high.
Urgency válidos: low, medium, high.

Considere:
- IT: VPN, senha, notebook, software, impressora, acesso técnico
- HR: férias, benefícios, documentos, treinamentos internos de RH
- Finance: reembolso, pagamento, relatório financeiro
- Facilities: ar-condicionado, mesa, cadeira, sala, manutenção predial
- Security: phishing, badge, alarme, incidente de segurança, acesso sensível
- Other: quando a demanda for ambígua ou não se encaixar bem

Retorne neste formato:
{
  "category": "...",
  "impact": "...",
  "urgency": "...",
  "summary": "...",
  "description": "..."
}

Funcionário:
{{$node["Get Employee"].json.name}} / {{$node["Get Employee"].json.department}}

Mensagem:
{{$node["Webhook"].json.body.message}}
```

#### 4. Node: `Structured Output`
- **Type:** Structured Output Parser, JSON Parser, ou `Set`/`Code` de validação, dependendo da versão
- **Objetivo:** garantir que o LLM produziu um JSON com os campos esperados

**Schema sugerido:**

```json
{
  "type": "object",
  "properties": {
    "category": { "type": "string", "enum": ["it", "hr", "finance", "facilities", "security", "other"] },
    "impact": { "type": "string", "enum": ["low", "medium", "high"] },
    "urgency": { "type": "string", "enum": ["low", "medium", "high"] },
    "summary": { "type": "string" },
    "description": { "type": "string" }
  },
  "required": ["category", "impact", "urgency", "summary", "description"]
}
```

#### 5. Node: `Priority API`
- **Type:** HTTP Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/api/v1/priority/check`
- **Send Body:** `JSON`
- **Headers:**

```text
Content-Type: application/json
X-Student-ID: grupo-07
X-Request-ID: n8n-triage-priority
```

**Body mapping:**

```json
{
  "employee_id": "={{ $node['Webhook'].json.body.employee_id }}",
  "category": "={{ $node['Structured Output'].json.category }}",
  "impact": "={{ $node['Structured Output'].json.impact }}",
  "urgency": "={{ $node['Structured Output'].json.urgency }}"
}
```

#### 6. Node: `Switch Category`
- **Type:** Switch
- **Value to Compare:** `={{ $node['Structured Output'].json.category }}`
- **Cases:**
  - `it`
  - `hr`
  - `finance`
  - `facilities`
  - `security`
  - fallback `other`

> Mesmo que todas as saídas voltem para o mesmo `Get Team`, o Switch é útil pedagogicamente para mostrar roteamento por categoria.

#### 7. Node: `Get Team`
- **Type:** HTTP Request
- **Method:** `GET`
- **URL:** `http://localhost:8000/api/v1/teams/{{$node['Structured Output'].json.category}}`
- **Headers:**

```text
X-Student-ID: grupo-07
X-Request-ID: n8n-triage-team
```

#### 8. Node: `Create Ticket`
- **Type:** HTTP Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/api/v1/tickets`
- **Send Body:** `JSON`
- **Headers:**

```text
Content-Type: application/json
X-Student-ID: grupo-07
X-Request-ID: n8n-triage-ticket
```

**Body mapping:**

```json
{
  "employee_id": "={{ $node['Webhook'].json.body.employee_id }}",
  "category": "={{ $node['Structured Output'].json.category }}",
  "impact": "={{ $node['Structured Output'].json.impact }}",
  "urgency": "={{ $node['Structured Output'].json.urgency }}",
  "summary": "={{ $node['Structured Output'].json.summary }}",
  "description": "={{ $node['Structured Output'].json.description }}",
  "source": "n8n"
}
```

#### 9. Node: `Respond to Webhook`
- **Type:** Respond to Webhook
- **Respond With:** `JSON`

**Response Body sugerido:**

```json
{
  "classification": "={{ $node['Structured Output'].json }}",
  "priority": "={{ $node['Priority API'].json }}",
  "team": "={{ $node['Get Team'].json }}",
  "ticket": "={{ $node['Create Ticket'].json }}"
}
```

### Output esperado

```json
{
  "classification": {
    "category": "it",
    "impact": "medium",
    "urgency": "high",
    "summary": "Acesso VPN indisponível",
    "description": "Funcionário relata falha de acesso à VPN e necessidade imediata para continuar o trabalho."
  },
  "priority": {
    "priority": "high",
    "sla_hours": 4,
    "requires_escalation": true,
    "rule": "medium_high_impact_urgency"
  },
  "team": {
    "category": "it",
    "team_name": "IT Support",
    "email": "it@example.com",
    "queue": "technical-support",
    "sla_default_hours": 4
  },
  "ticket": {
    "ticket_id": "TK-1001",
    "status": "open"
  }
}
```

### Descrição de screenshot

- Workflow maior, com nove nodes.
- `Switch Category` ao centro com saídas nomeadas por categoria.
- `Create Ticket` exibindo body JSON com expressões n8n.
- `Respond to Webhook` consolidando quatro objetos na resposta final.

---

## WORKFLOW 3 — Error Handling

### Objetivo

Testar timeout, retry e fallback ao consumir endpoints problemáticos do laboratório.

### Ordem de conexão principal

```text
Manual Trigger → Call Slow Endpoint → Fallback / Error Branch
```

### Cenários para testar

- `GET /api/v1/lab/slow?seconds=10`
- `GET /api/v1/lab/error`
- `GET /api/v1/lab/rate-limit`

### Nodes

#### 1. Node: `Manual Trigger`
- **Type:** Manual Trigger

#### 2. Node: `Call Slow Endpoint`
- **Type:** HTTP Request
- **Method:** `GET`
- **URL:** `http://localhost:8000/api/v1/lab/slow?seconds=10`
- **Headers:**

```text
X-Student-ID: grupo-07
X-Request-ID: n8n-error-slow
```

- **Timeout:** configure um valor curto, por exemplo `3000 ms`, para forçar falha didática
- **Retry On Fail:** habilite se sua versão do n8n oferecer essa opção no node
- **Max Tries:** `2` ou `3`

#### 3. Node: `Error Trigger` ou ramo alternativo de erro
- **Type:** Error Trigger
- Use quando quiser capturar falhas de execução do workflow inteiro

#### 4. Node: `Fallback Response`
- **Type:** Set, Edit Fields, ou outro node simples de resposta interna

**Payload de fallback sugerido:**

```json
{
  "status": "fallback",
  "message": "Serviço temporariamente indisponível. Tente novamente em instantes.",
  "original_node": "Call Slow Endpoint"
}
```

### Teste de `/lab/error`

Troque a URL para:

```text
http://localhost:8000/api/v1/lab/error
```

Resposta esperada:

```json
{
  "detail": "Simulated internal server error"
}
```

### Teste de `/lab/rate-limit`

Troque a URL para:

```text
http://localhost:8000/api/v1/lab/rate-limit
```

Faça quatro execuções rápidas com o mesmo `X-Student-ID`.

Na quarta chamada, a expectativa didática é um `429` com header:

```text
Retry-After: 10
```

e body semelhante a:

```json
{
  "detail": "Too many requests",
  "retry_after_seconds": 10
}
```

### Estratégia de retry

- tentativa 1: chamada normal
- tentativa 2: retry automático
- tentativa 3: fallback controlado

### Descrição de screenshot

- `Manual Trigger` ligado ao `HTTP Request`.
- Painel do node mostrando timeout curto.
- Outro workflow com `Error Trigger` recebendo execuções com falha.

---

## WORKFLOW 4 — Human-in-the-Loop

### Objetivo

Criar uma solicitação de acesso e separar automaticamente casos autoaprovados de casos que exigem aprovação humana.

### Ordem de conexão

```text
Webhook → Get Employee → LLM Risk Classifier → Create Access Request → IF Requires Approval → Wait / Approval Branch → Respond
```

### Payload de entrada sugerido

```json
{
  "employee_id": "EMP006",
  "message": "Preciso de acesso administrativo ao painel de segurança para investigar alertas hoje.",
  "resource": "Security Admin Console"
}
```

### Nodes

#### 1. Node: `Webhook`
- **Type:** Webhook
- **Method:** `POST`
- **Path:** `flowdesk-access-request`
- **Response Mode:** `Using Respond to Webhook Node`

#### 2. Node: `Get Employee`
- **Type:** HTTP Request
- **Method:** `GET`
- **URL:** `http://localhost:8000/api/v1/employees/{{$json.body.employee_id}}`

#### 3. Node: `LLM Risk Classifier`
- **Type:** OpenAI Chat / AI Chat Model

**Prompt sugerido:**

```text
Classifique o risco da solicitação de acesso abaixo e retorne SOMENTE JSON.

Riscos válidos: low, medium, high.

Retorne:
{
  "risk": "low|medium|high",
  "justification": "texto curto para registrar na API"
}

Funcionário: {{$node["Get Employee"].json.name}}
Mensagem: {{$node["Webhook"].json.body.message}}
Recurso: {{$node["Webhook"].json.body.resource}}
```

#### 4. Node: `Create Access Request`
- **Type:** HTTP Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/api/v1/access-requests`
- **Headers:**

```text
Content-Type: application/json
X-Student-ID: grupo-07
X-Request-ID: n8n-access-create
```

**Body mapping:**

```json
{
  "employee_id": "={{ $node['Webhook'].json.body.employee_id }}",
  "resource": "={{ $node['Webhook'].json.body.resource }}",
  "justification": "={{ $node['LLM Risk Classifier'].json.justification }}",
  "risk": "={{ $node['LLM Risk Classifier'].json.risk }}"
}
```

#### 5. Node: `IF Requires Approval`
- **Type:** IF
- **Condition:** `={{ $node['Create Access Request'].json.requires_human_approval === true }}`

### Branch A — Auto-approved

Se `false`, responda imediatamente:

```json
{
  "status": "auto-approved",
  "request": "={{ $node['Create Access Request'].json }}"
}
```

### Branch B — Approval branch

#### 6. Node: `Wait for Human Review`
- **Type:** Wait
- Use um tempo fixo curto para simulação, ou espere callback/manual resume

#### 7. Node: `Approve Access Request`
- **Type:** HTTP Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/api/v1/access-requests/{{$node['Create Access Request'].json.request_id}}/approve`
- **Headers:**

```text
Content-Type: application/json
X-Student-ID: grupo-07
X-Request-ID: n8n-access-approve
```

**Body mapping de aprovação:**

```json
{
  "approved_by": "manager@flowdesk.lab",
  "decision": "approved",
  "decision_comment": "Approved in classroom simulation after human review."
}
```

#### 8. Node: `Respond`
- **Type:** Respond to Webhook

**Response Body sugerido:**

```json
{
  "employee": "={{ $node['Get Employee'].json }}",
  "risk_assessment": "={{ $node['LLM Risk Classifier'].json }}",
  "access_request": "={{ $node['Create Access Request'].json }}",
  "final_decision": "={{ $node['Approve Access Request'].json }}"
}
```

### Output esperado

#### Caso low risk

```json
{
  "request_id": "AR-501",
  "status": "auto_approved",
  "requires_human_approval": false,
  "approved_by": "system",
  "decision": "auto_approved"
}
```

#### Caso medium/high risk

```json
{
  "request_id": "AR-502",
  "status": "pending_approval",
  "requires_human_approval": true
}
```

### Descrição de screenshot

- `IF Requires Approval` dividindo o fluxo em dois ramos.
- Ramo inferior com `Wait` seguido de `Approve Access Request`.
- `Respond` final consolidando a solicitação criada e a decisão.

---

## Expressões úteis no n8n

```javascript
{{$json.body.employee_id}}
{{$json.body.message}}
{{$node["Get Employee"].json.name}}
{{$node["Structured Output"].json.category}}
{{$node["Priority API"].json.priority}}
{{$node["Create Ticket"].json.ticket_id}}
{{$node["Create Access Request"].json.request_id}}
```

## Dicas práticas

- mantenha `X-Student-ID` fixo por grupo
- use `X-Request-ID` para rastrear chamadas durante a aula
- comece com `Workflow 1` antes de adicionar LLM, Switch e Wait
- teste os endpoints de erro separadamente para visualizar timeouts e 429
