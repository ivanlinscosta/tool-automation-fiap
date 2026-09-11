# Make Lab: FIAP Student Desk Lab

Este guia descreve como implementar os cenários de automação para a Central Inteligente de Solicitações Acadêmicas utilizando o Make (antigo Integromat).

## Visão Geral do Cenário
O objetivo é reproduzir a lógica de atendimento inteligente:
1. Receber a mensagem.
2. Identificar o aluno.
3. Classificar a intenção com IA.
4. Buscar na base de conhecimento.
5. Decidir entre responder ou criar uma solicitação.

## Módulos Necessários
- **Custom Webhook:** Ponto de entrada para a mensagem do aluno.
- **HTTP - Make a request:** Para todas as interações com a API.
- **OpenAI (ou outro módulo de LLM):** Para classificação e geração de resposta.
- **Router:** Para desviar o fluxo entre resposta automática e criação de solicitação.
- **JSON - Parse JSON:** Para processar as saídas estruturadas do LLM.

## Estrutura do Cenário Principal

### 1. Entrada e Identificação
- **Custom Webhook:** Recebe `student_id` e `message`.
- **HTTP (Get Student):** 
  - Method: `GET`
  - URL: `http://localhost:8000/api/v1/students/{{student_id}}`
  - Headers: `X-Student-ID: seu-grupo`

### 2. Inteligência e Classificação
- **OpenAI (Create a Chat Completion):**
  - Prompt: Peça para classificar a mensagem em categoria, intenção, impacto, urgência e gerar uma `search_query`.
  - Output: JSON estruturado.
- **JSON (Parse JSON):** Transforma a string do LLM em campos mapeáveis no Make.

### 3. Busca de Conhecimento
- **HTTP (Knowledge Search):**
  - Method: `GET`
  - URL: `http://localhost:8000/api/v1/knowledge/search?q={{search_query}}&category={{category}}`

### 4. Roteamento (Router)
Adicione um **Router** após a busca.

#### Rota A: Resposta Automática (Filtro: `needs_human` é falso E resultados encontrados)
- **OpenAI (Generate Response):** Gera a resposta baseada nos artigos.
- **HTTP (Register Interaction):** POST `/api/v1/interactions`.
- **Webhook Response:** Devolve a resposta ao aluno.

#### Rota B: Criar Solicitação (Filtro: `needs_human` é verdadeiro OU nenhum resultado encontrado)
- **HTTP (Priority Check):** POST `/api/v1/priority/check`.
- **HTTP (Get Department):** GET `/api/v1/departments/{{category}}`.
- **HTTP (Create Request):** POST `/api/v1/requests`.
- **Webhook Response:** Devolve o número do protocolo.

## Tratamento de Erros no Make
- **Directives:** Utilize as diretivas `Break` ou `Retry` nos módulos HTTP para lidar com instabilidades.
- **Error Handler Route:** Clique com o botão direito no módulo HTTP e selecione "Add error handler" para tratar erros 429 ou 500 de forma personalizada.

## Dicas de Configuração
- **Headers:** Lembre-se de sempre enviar o `Content-Type: application/json` em requisições POST.
- **Mapping:** Use o painel de mapeamento do Make para arrastar os campos do `Parse JSON` para os módulos seguintes.
- **Filtros:** No Router, configure as condições de filtragem clicando na linha que conecta os módulos.
