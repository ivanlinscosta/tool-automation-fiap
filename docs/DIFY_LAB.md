# Dify Lab: FIAP Student Desk Lab

Este guia descreve como integrar a FIAP Student Desk Lab API ao Dify para criar agentes inteligentes e fluxos de trabalho automatizados.

## Importando a API como Tool

1. **Obtenha o OpenAPI Spec:**
   Acesse `http://localhost:8000/openapi.json` (ou a URL do seu deploy no Railway) e salve o conteúdo ou copie o link.

2. **Configuração no Dify:**
   - Vá em **Tools** > **Custom Tools** > **Create Custom Tool**.
   - Nome: `FIAP_Student_Desk`.
   - Schema: Cole o conteúdo do `openapi.json`.
   - Privacy Policy: `https://fiap.com.br` (fictício).

3. **Autenticação e Headers:**
   - Se desejar fixar o grupo, adicione o header `X-Student-ID` nas configurações da Tool.

## Configurando um Agente (Chatflow)

### 1. Seleção de Ferramentas (Tools)
Habilite as seguintes ferramentas para o seu agente:
- `get_student`: Para identificar o aluno.
- `search_knowledge`: Para buscar respostas na base de conhecimento.
- `get_department`: Para saber para onde encaminhar solicitações.
- `check_priority`: Para definir a urgência.
- `create_request`: Para abrir solicitações formais.
- `register_interaction`: Para salvar o histórico.

### 2. System Prompt (Instruções do Agente)
```text
Você é o Assistente Virtual da FIAP Student Desk. Seu objetivo é ajudar alunos com dúvidas acadêmicas.

Siga rigorosamente este protocolo:
1. Identifique o aluno usando a ferramenta 'get_student' com o ID fornecido.
2. Pesquise a dúvida na base de conhecimento usando 'search_knowledge'.
3. Se encontrar a resposta nos artigos, responda ao aluno de forma clara e registre a conversa com 'register_interaction'.
4. Se NÃO encontrar a resposta ou se for um pedido de documento/ajuste financeiro:
   a. Verifique a prioridade com 'check_priority'.
   b. Identifique o departamento com 'get_department'.
   c. Crie uma solicitação formal com 'create_request'.
   d. Informe o número do protocolo ao aluno.

IMPORTANTE: Nunca invente informações. Se não souber, use as ferramentas ou encaminhe para um humano.
```

### 3. Anti-Hallucination
Adicione nas instruções:
- "Responda apenas com base nos artigos retornados pela ferramenta search_knowledge."
- "Se a ferramenta retornar vazio, não tente adivinhar a política da FIAP."

## Workflow Mode no Dify
Para maior controle, você pode usar o modo **Workflow** em vez de **Chatflow**:
- **Start Node:** Recebe `student_id` e `query`.
- **Tool Node (Get Student):** Busca dados.
- **LLM Node (Classifier):** Decide o próximo passo.
- **Condition Node:** Se `search` ou `request`.
- **Tool Node (Search/Request):** Executa a ação.
- **End Node:** Resposta final.

## Dicas de Laboratório
- **Variáveis:** Use variáveis de sistema do Dify para capturar o `conversation_id` e associar aos logs da API.
- **Logs:** Acompanhe as chamadas na aba **Logs** do Dify para depurar o comportamento do agente.
