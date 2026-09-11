# n8n Lab: FIAP Student Desk Lab

Este guia descreve como implementar os workflows de automação para a Central Inteligente de Solicitações Acadêmicas utilizando o n8n.

## Workflow 1: API Explorer
**Objetivo:** Familiarizar-se com os endpoints da API.
- Utilize o nó **HTTP Request**.
- Experimente chamadas GET para:
  - `/api/v1/students`
  - `/api/v1/departments`
  - `/api/v1/knowledge`
- Observe a estrutura do JSON retornado.

## Workflow 2: Student Request + Automatic Answer
**Objetivo:** Responder automaticamente dúvidas que constam na base de conhecimento.

**Estrutura:**
1. **Webhook:** Recebe `student_id` e `message`.
2. **HTTP Request (GET Student):** Busca dados em `/api/v1/students/{{$json.student_id}}`.
3. **LLM Classification:** Nó de IA que analisa a mensagem e retorna um JSON estruturado:
   ```json
   {
     "category": "digital_learning",
     "intent": "report_problem",
     "impact": "high",
     "urgency": "high",
     "summary": "Aluno sem acesso ao portal",
     "search_query": "problemas acesso portal ambiente virtual",
     "needs_human": false
   }
   ```
4. **HTTP Request (Knowledge Search):** GET `/api/v1/knowledge/search?q={{$json.search_query}}&category={{$json.category}}`.
5. **IF Node:** Verifica se `needs_human == false` E se foram encontrados resultados na busca.
6. **LLM Grounded Response:** Se verdadeiro, utiliza os artigos encontrados como contexto para gerar uma resposta amigável.
7. **HTTP Request (Register Interaction):** POST `/api/v1/interactions` com a resposta gerada.
8. **Respond to Webhook:** Envia a resposta final para o aluno.

## Workflow 3: Student Request + Create Request
**Objetivo:** Criar uma solicitação formal quando a base de conhecimento é insuficiente.

**Estrutura:**
- Segue o fluxo anterior até o nó **IF**.
- **IF (Falso):** Se `needs_human == true` OU nenhum resultado relevante foi encontrado.
1. **HTTP Request (Priority Check):** POST `/api/v1/priority/check` enviando categoria, impacto e urgência.
2. **HTTP Request (Get Department):** GET `/api/v1/departments/{{$json.category}}`.
3. **HTTP Request (Create Request):** POST `/api/v1/requests` com os detalhes da solicitação.
4. **Respond to Webhook:** Informa ao aluno o número do protocolo gerado.

## Workflow 4: Error Handling
**Objetivo:** Tornar o workflow resiliente a falhas.
- **Timeout:** Configure o nó HTTP Request para falhar após X segundos e use o nó **Wait** seguido de uma retentativa.
- **Rate Limit:** Trate o erro 429 (Too Many Requests) lendo o header `Retry-After`.
- **Error Trigger:** Utilize o nó **Error Trigger** para capturar falhas genéricas e notificar (ex: via Slack ou Email).

## Workflow 5: Human-in-the-Loop
**Objetivo:** Gerenciar aprovações humanas para solicitações críticas.
1. **POST /api/v1/approval-requests:** Cria uma solicitação de aprovação.
2. **Wait for Webhook:** O workflow pausa e aguarda um webhook de retorno.
3. **Human Decision:** Um humano acessa o sistema (ou interface simulada) e toma uma decisão.
4. **POST /api/v1/approval-requests/{{id}}/decision:** O sistema de aprovação chama o webhook de retorno do n8n.
5. **Resume Workflow:** O n8n processa a decisão e atualiza a solicitação original via PATCH `/api/v1/requests/{{id}}`.

## Workflow 6: AI Agent + Tools
**Objetivo:** Criar um agente autônomo que decide quais ferramentas usar.
- Utilize o nó **AI Agent**.
- Configure as seguintes ferramentas (Tools) como HTTP Requests:
  - `get_student`: Busca dados do aluno.
  - `search_knowledge`: Pesquisa na base de conhecimento.
  - `get_department`: Identifica o departamento responsável.
  - `check_priority`: Calcula a prioridade.
  - `create_request`: Registra uma nova solicitação.
  - `register_interaction`: Registra o histórico de conversa.
- **System Prompt:** "Você é o assistente virtual da FIAP. Use as ferramentas disponíveis para ajudar o aluno. Sempre verifique os dados do aluno antes de prosseguir."

---

## Exemplos de Prompts

### Classification Prompt
```text
Analise a seguinte mensagem de um aluno da FIAP e extraia as informações em formato JSON.
Categorias: digital_learning, academic_services, finance, career, campus_access.
Intenções: ask_question, request_document, report_problem, financial_question, career_question.

Mensagem: "{{$json.message}}"

JSON de saída esperado:
{
  "category": "string",
  "intent": "string",
  "impact": "low|medium|high",
  "urgency": "low|medium|high",
  "summary": "string",
  "search_query": "string",
  "needs_human": boolean
}
```

### Grounded Response Prompt
```text
Você é o assistente da FIAP. Responda à dúvida do aluno utilizando EXCLUSIVAMENTE as informações dos artigos de conhecimento fornecidos abaixo. Se a informação não estiver nos artigos, diga que não sabe e que encaminhará para um atendente humano.

Artigos:
{{$json.knowledge_results}}

Pergunta do aluno:
"{{$node["Webhook"].json["message"]}}"
```
