# FIAP Student Desk Lab + n8n

> **Aviso:** Este projeto é um laboratório educacional fictício e não representa sistemas ou políticas oficiais da FIAP.

## Visão geral

Esta pasta entrega workflows pedagógicos para a **FIAP Student Desk Lab API**:

1. **01-api-explorer**: consulta students, departments e knowledge.
2. **02-intelligent-triage**: recebe mensagem do aluno, classifica, busca knowledge e cria solicitação.
3. **03-error-handling**: explora timeout, erro 500, rate limit e fallback.
4. **04-human-in-the-loop**: cria solicitação de aprovação e simula decisão humana.

## Pré-requisitos

- n8n em execução
- FIAP Student Desk Lab API em `http://localhost:8000`
- Header fixo por grupo: `X-Student-ID: grupo-01`
- Opcional: credencial de LLM no n8n

## Convenções

- Base URL: `http://localhost:8000`
- Student de teste: `STU001`
- Header `X-Request-ID`: rastreabilidade didática
- Em nodes com IA, troque `YOUR_CREDENTIAL_ID` e `YOUR_CREDENTIAL_NAME`

## Como importar

1. Abra o n8n.
2. Vá em **Workflows**.
3. Escolha **Import from File**.
4. Selecione um dos JSONs desta pasta.
5. Revise URLs, headers e nodes placeholder.
6. Execute manualmente ou ative o webhook.

## Workflow 1 — API Explorer

### Objetivo

Demonstrar o fluxo mínimo: **Webhook → HTTP Request → Respond to Webhook**.

### Entrada

```json
{
  "student_id": "STU001"
}
```

### Passo a passo

1. Crie um **Webhook** com método `POST` e path `fiap-student-desk-explorer`.
2. Adicione um **HTTP Request** `Get Student`: `GET /api/v1/students/{{$json.body.student_id}}`.
3. Adicione headers: `X-Student-ID: grupo-01`.
4. Adicione **Respond to Webhook** retornando o JSON do student.

## Workflow 2 — Intelligent Triage

### Objetivo

Classificação de linguagem natural, busca na knowledge base e criação de solicitação.

### Fluxo

```
Webhook → Get Student → LLM Classifier → Knowledge Search → IF can_answer?
  SIM → LLM Grounded Response → Register Interaction → Respond
  NÃO → Priority Check → Get Department → Create Request → Respond with protocol
```

### Entrada

```json
{
  "student_id": "STU001",
  "message": "Não consigo acessar o ambiente para enviar meu projeto."
}
```

### Prompt do LLM Classifier

```text
Você é um classificador de solicitações acadêmicas de um laboratório fictício relacionado à FIAP.

Retorne SOMENTE JSON válido:
{
  "category": "academic_services|digital_learning|finance|career|campus_access|technology|student_experience|library|other",
  "intent": "ask_information|report_problem|request_document|request_access|financial_question|career_question|other",
  "impact": "low|medium|high",
  "urgency": "low|medium|high",
  "summary": "resumo curto",
  "search_query": "palavras-chave para busca na knowledge base",
  "needs_human": false
}

Aluno: {{$node["Get Student"].json.name}} / {{$node["Get Student"].json.course}}
Mensagem: {{$node["Webhook"].json.body.message}}

Não invente políticas FIAP.
```

### Prompt do LLM Grounded Response

```text
Responda à solicitação utilizando EXCLUSIVAMENTE o conteúdo de contexto abaixo.

O conteúdo é fictício e faz parte de um laboratório educacional.

Não invente políticas FIAP.

Se o contexto não responder adequadamente, retorne:
{"can_answer": false}

Caso possa responder:
{"can_answer": true, "answer": "sua resposta aqui"}

CONTEXTO:
{{knowledge_results}}

PERGUNTA:
{{student_message}}
```

## Workflow 3 — Error Handling

### Objetivo

Praticar comportamento resiliente: timeout, 500, 429 e fallback.

### Cenários

- `GET /api/v1/lab/slow?seconds=10` → timeout
- `GET /api/v1/lab/error` → erro 500
- `GET /api/v1/lab/rate-limit` → 429 após 3 chamadas

## Workflow 4 — Human-in-the-Loop

### Objetivo

Separar casos autoaprovados (baixo risco) de casos que exigem revisão humana.

### Fluxo

```
Webhook → Get Student → Risk Assessment → Create Approval Request
  → IF requires_human?
    SIM → Wait → Decide Approval → Respond
    NÃO → Respond auto-approved
```

### Entrada

```json
{
  "student_id": "STU002",
  "request_type": "privileged_lab_access",
  "justification": "Preciso acessar ambiente restrito para atividade.",
  "risk": "high"
}
```

## Troubleshooting

### 1. 422 ao criar request

Envie: `student_id`, `category`, `summary`, `description`, `source`. O campo `priority` é opcional.

### 2. 404 em student ou department

Use IDs existentes: `STU001`-`STU020` para students, categorias válidas para departments.

### 3. 429 em lab/rate-limit

Aguarda após 3 chamadas com o mesmo `X-Student-ID`. Aguarde `Retry-After`.

## Expressões úteis

```javascript
{{$json.body.student_id}}
{{$json.body.message}}
{{$node["Get Student"].json.name}}
{{$node["Knowledge Search"].json.results}}
{{$node["Priority Check"].json.priority}}
{{$node["Create Request"].json.protocol}}
```

## Sugestão de uso em aula

1. Comece pelo **01-api-explorer**.
2. Avance para **02-intelligent-triage**.
3. Demonstre **03-error-handling**.
4. Finalize com **04-human-in-the-loop**.
