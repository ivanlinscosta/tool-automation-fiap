# FlowDesk Lab + n8n

## Visão geral

Esta pasta entrega quatro workflows pedagógicos para a **FlowDesk Lab API**:

1. **01-api-explorer**: recebe um `employee_id`, consulta a API e devolve os dados do colaborador.
2. **02-intelligent-triage**: recebe uma mensagem em linguagem natural, classifica categoria/impacto/urgência, calcula prioridade, busca o time e abre um ticket.
3. **03-error-handling**: explora timeout, erro 500, rate limit e fallback didático.
4. **04-human-in-the-loop**: cria solicitação de acesso, separa casos autoaprovados e simula aprovação humana.

Os arquivos JSON foram montados no **formato padrão de export do n8n** (`nodes`, `connections`, `settings`, `id`, `versionId`, `tags`). Para maximizar compatibilidade em sala, os passos de IA usam nodes placeholder de `Set` quando o formato exato do node de LLM pode variar por versão. O README abaixo explica como substituir esses placeholders por nodes de IA reais.

## Pré-requisitos

- n8n em execução
- FlowDesk Lab API em `http://localhost:8000`
- Header fixo por grupo, por exemplo `X-Student-ID: grupo-01`
- Opcional: credencial de LLM no n8n (OpenAI, Azure OpenAI ou outro provider compatível)

## Convenções usadas

- Base URL: `http://localhost:8000`
- Employee de teste principal: `EMP001`
- Access request de teste: `EMP002`
- Header `X-Request-ID`: usado para rastreabilidade didática
- Em imports com IA, troque `YOUR_CREDENTIAL_ID` e `YOUR_CREDENTIAL_NAME`

## Como importar

1. Abra o n8n.
2. Vá em **Workflows**.
3. Escolha **Import from File**.
4. Selecione um dos JSONs desta pasta.
5. Revise URLs, headers e nodes placeholder.
6. Execute manualmente ou ative o webhook quando apropriado.

## Workflow 1 — API Explorer

### Objetivo

Demonstrar o fluxo mínimo: **Webhook → HTTP Request → Respond to Webhook**.

### Entrada esperada

```json
{
  "employee_id": "EMP001"
}
```

### Passo a passo manual

1. Crie um **Webhook** com método `POST` e path `flowdesk-api-explorer`.
2. Configure o webhook para responder usando **Respond to Webhook**.
3. Adicione um **HTTP Request** chamado `Get Employee`.
4. Use método `GET` e URL `http://localhost:8000/api/v1/employees/{{$json.body.employee_id}}`.
5. Adicione headers:
   - `X-Student-ID: grupo-01`
   - `X-Request-ID: n8n-explorer-001`
6. Adicione **Respond to Webhook** retornando o JSON do colaborador.

### Configuração detalhada dos nodes

#### Webhook
- Type: `n8n-nodes-base.webhook`
- Method: `POST`
- Path: `flowdesk-api-explorer`
- Response mode: usar node de resposta

#### Get Employee
- Type: `n8n-nodes-base.httpRequest`
- Method: `GET`
- URL: `http://localhost:8000/api/v1/employees/{{$json.body.employee_id}}`
- Response: JSON

#### Respond to Webhook
- Type: `n8n-nodes-base.respondToWebhook`
- Body sugerido:

```json
{
  "employee": "={{ $json }}"
}
```

### Saída esperada

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

## Workflow 2 — Intelligent Triage

### Objetivo

Demonstrar classificação de linguagem natural, cálculo determinístico de prioridade e criação de ticket.

### Fluxo lógico

`Webhook → Get Employee → LLM Classifier → Structured Output → Priority API → Switch Category → Get Team → Create Ticket → Respond to Webhook`

### Entrada sugerida

```json
{
  "employee_id": "EMP001",
  "message": "Meu notebook não conecta ao Wi-Fi desde ontem e tenho uma reunião importante daqui a uma hora."
}
```

### Como usar o JSON importado

O workflow exportado usa dois nodes `Set` como placeholders:

- `LLM Classifier Placeholder`
- `Structured Output Placeholder`

Eles servem para o workflow importar de forma segura mesmo em ambientes sem nodes de IA habilitados.

### Como substituir por IA real

1. Remova o node `LLM Classifier Placeholder`.
2. Adicione um node de chat/LLM disponível na sua versão do n8n.
3. Configure a credencial com `YOUR_CREDENTIAL_ID`.
4. Use o seguinte prompt:

```text
Você é um classificador de triagem do FlowDesk Lab.

Retorne SOMENTE JSON válido com:
{
  "category": "it|hr|finance|facilities|security|other",
  "impact": "low|medium|high",
  "urgency": "low|medium|high",
  "summary": "texto curto",
  "description": "texto detalhado"
}

Funcionário: {{$node["Get Employee"].json.name}} / {{$node["Get Employee"].json.department}}
Mensagem: {{$node["Webhook"].json.body.message}}
```

5. Substitua `Structured Output Placeholder` por um parser/validator JSON, ou um node `Code`/`Set` que valide os campos.

### Configuração detalhada dos passos HTTP

#### Priority API
- Method: `POST`
- URL: `http://localhost:8000/api/v1/priority/check`
- Headers:
  - `Content-Type: application/json`
  - `X-Student-ID: grupo-01`
  - `X-Request-ID: n8n-triage-priority`
- Body:

```json
{
  "employee_id": "={{ $node['Webhook'].json.body.employee_id }}",
  "category": "={{ $node['Structured Output Placeholder'].json.category }}",
  "impact": "={{ $node['Structured Output Placeholder'].json.impact }}",
  "urgency": "={{ $node['Structured Output Placeholder'].json.urgency }}"
}
```

#### Get Team
- Method: `GET`
- URL: `http://localhost:8000/api/v1/teams/{{$node['Structured Output Placeholder'].json.category}}`

#### Create Ticket
- Method: `POST`
- URL: `http://localhost:8000/api/v1/tickets`
- Body:

```json
{
  "employee_id": "={{ $node['Webhook'].json.body.employee_id }}",
  "category": "={{ $node['Structured Output Placeholder'].json.category }}",
  "impact": "={{ $node['Structured Output Placeholder'].json.impact }}",
  "urgency": "={{ $node['Structured Output Placeholder'].json.urgency }}",
  "summary": "={{ $node['Structured Output Placeholder'].json.summary }}",
  "description": "={{ $node['Structured Output Placeholder'].json.description }}",
  "source": "n8n"
}
```

### Saídas esperadas por etapa

- **Get Employee**: colaborador retornado pela API
- **Structured Output**: objeto com `category`, `impact`, `urgency`, `summary`, `description`
- **Priority API**: prioridade calculada, SLA e regra
- **Get Team**: fila e time responsável
- **Create Ticket**: ticket criado com `ticket_id`

### Exemplo de resposta final

```json
{
  "classification": {
    "category": "it",
    "impact": "high",
    "urgency": "high",
    "summary": "Falha de conectividade no notebook",
    "description": "Notebook não conecta ao Wi-Fi desde ontem. Funcionário tem reunião importante em 1 hora."
  },
  "priority": {
    "priority": "critical",
    "sla_hours": 1,
    "requires_escalation": true,
    "rule": "high_high_impact_urgency"
  },
  "team": {
    "category": "it",
    "team_name": "IT Support",
    "queue": "technical-support"
  },
  "ticket": {
    "ticket_id": "TK-1001",
    "status": "open"
  }
}
```

## Workflow 3 — Error Handling

### Objetivo

Praticar comportamento resiliente em integrações: timeout, 500, 429 e fallback.

### Cenários de teste

- `GET /api/v1/lab/slow?seconds=10`
- `GET /api/v1/lab/error`
- `GET /api/v1/lab/rate-limit`

### Montagem manual

1. Comece com **Manual Trigger**.
2. Adicione um **HTTP Request** apontando para um endpoint de falha.
3. Para timeout, configure a URL `http://localhost:8000/api/v1/lab/slow?seconds=10`.
4. Se sua versão do n8n permitir, configure timeout em `3000 ms` e retry em `2` ou `3` tentativas.
5. Após a falha, envie o fluxo para um node `Set` com payload de fallback.

### Payload de fallback sugerido

```json
{
  "status": "fallback",
  "message": "Serviço temporariamente indisponível. Tente novamente em instantes.",
  "original_node": "Call Slow Endpoint"
}
```

### Resultado esperado por cenário

- **slow**: timeout ou resposta atrasada
- **error**: JSON com `detail: Simulated internal server error`
- **rate-limit**: após 4 chamadas rápidas com o mesmo `X-Student-ID`, retorno `429` e header `Retry-After: 10`

## Workflow 4 — Human-in-the-Loop

### Objetivo

Separar solicitações de acesso de baixo risco (autoaprovadas) de casos médios/altos que exigem revisão humana.

### Fluxo lógico

`Webhook → Get Employee → Risk Classifier → Create Access Request → IF Requires Approval → Wait → Approve Access Request → Respond`

### Entrada sugerida

```json
{
  "employee_id": "EMP002",
  "message": "Preciso de acesso administrativo ao production-server para aplicar um patch crítico hoje.",
  "resource": "production-server"
}
```

### Placeholder de risco

O JSON importado usa um node `Set` chamado `Risk Classifier Placeholder`. Se quiser IA real:

1. Troque esse node por um node de LLM.
2. Use um prompt que retorne apenas:

```json
{
  "risk": "low|medium|high",
  "justification": "texto curto"
}
```

3. Faça o mapping para `Create Access Request`.

### Configuração detalhada

#### Create Access Request
- Method: `POST`
- URL: `http://localhost:8000/api/v1/access-requests`
- Body:

```json
{
  "employee_id": "={{ $node['Webhook'].json.body.employee_id }}",
  "resource": "={{ $node['Webhook'].json.body.resource }}",
  "justification": "={{ $node['Risk Classifier Placeholder'].json.justification }}",
  "risk": "={{ $node['Risk Classifier Placeholder'].json.risk }}"
}
```

#### IF Requires Approval
- Condição: `={{ $node['Create Access Request'].json.requires_human_approval === true }}`

#### Approve Access Request
- Method: `POST`
- URL: `http://localhost:8000/api/v1/access-requests/{{$node['Create Access Request'].json.request_id}}/approve`
- Body:

```json
{
  "approved_by": "professor@fiap.com.br",
  "decision": "approved",
  "decision_comment": "Approved in classroom simulation after human review."
}
```

### Saída esperada

#### Caso low risk

```json
{
  "status": "auto_approved",
  "requires_human_approval": false,
  "approved_by": "system",
  "decision": "auto_approved"
}
```

#### Caso medium/high risk

```json
{
  "status": "approved",
  "requires_human_approval": true,
  "approved_by": "professor@fiap.com.br",
  "decision": "approved"
}
```

## Troubleshooting

### 1. 422 ao criar ticket

Causa comum: enviar `priority` no body. A API real calcula a prioridade automaticamente e exige:

- `employee_id`
- `category`
- `impact`
- `urgency`
- `summary`
- `description`
- `source`

### 2. 422 ao aprovar access request

Causa comum: usar `decision: approve` ou campo `comment`.

Formato válido:

```json
{
  "approved_by": "professor@fiap.com.br",
  "decision": "approved",
  "decision_comment": "Aprovado para demonstração em sala de aula."
}
```

### 3. 404 em Get Ticket ou Get Access Request

Use um ID realmente existente no banco atual. Se o lab foi resetado, o primeiro ticket criado tende a ser `TK-1001` e a primeira solicitação `AR-501`.

### 4. 429 em lab/rate-limit

É esperado após múltiplas chamadas com o mesmo `X-Student-ID`. Aguarde o valor indicado em `Retry-After`.

### 5. Workflow importou, mas o node de IA não existe

Isso pode acontecer por diferença de versão do n8n. Nesse caso:

- mantenha o workflow importado
- troque apenas o placeholder `Set`
- conecte manualmente o node de IA equivalente na sua instalação

### 6. A API local não responde

Verifique se o FastAPI está de pé em `http://localhost:8000`:

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{
  "status": "ok",
  "service": "flowdesk-lab-api",
  "version": "1.0.0"
}
```

## Expressões úteis

```javascript
{{$json.body.employee_id}}
{{$json.body.message}}
{{$json.body.resource}}
{{$node["Get Employee"].json.name}}
{{$node["Priority API"].json.priority}}
{{$node["Create Ticket"].json.ticket_id}}
{{$node["Create Access Request"].json.request_id}}
```

## Sugestão de uso em aula

1. Comece pelo **01-api-explorer**.
2. Depois avance para **02-intelligent-triage**.
3. Em seguida demonstre **03-error-handling**.
4. Finalize com **04-human-in-the-loop** para mostrar aprovação humana e governança.
