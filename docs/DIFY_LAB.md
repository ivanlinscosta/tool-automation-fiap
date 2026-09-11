# FlowDesk Lab com Dify

## Objetivo

Usar a FlowDesk Lab API como conjunto de tools em aplicações Dify, tanto no modo Agent quanto no modo Workflow.

## Fontes do contrato

### Opção 1 — OpenAPI exposto pela aplicação

Use:

```text
http://localhost:8000/openapi.json
```

> No estado atual do repositório, a referência segura e direta para importação é o endpoint `openapi.json` da aplicação em execução.

## Como importar a API como Tool

1. Abra o Dify.
2. Crie ou edite uma aplicação.
3. Vá até a área de **Tools**.
4. Escolha importar via **OpenAPI**.
5. Informe a URL `http://localhost:8000/openapi.json`.
6. Revise os endpoints detectados.
7. Publique as tools necessárias para o agente.

Se o Dify detectar menos operações do que o esperado, valide primeiro o contrato realmente exposto em `/openapi.json` antes de seguir com a configuração do agente.

## Tools recomendadas

Para os exercícios iniciais, habilite pelo menos:

- `get_employee`
- `get_team`
- `check_priority`
- `create_ticket`

Opcionalmente, adicione também:

- `list_tickets`
- `create_access_request`
- `approve_access_request`
- `list_events`

## Configuração de headers

Se a importação permitir headers default, configure:

```text
X-Student-ID: grupo-07
```

Se preferir, exponha esse valor como variável do app para cada grupo de alunos.
Lembre-se: `X-Student-ID` ajuda no contexto pedagógico, mas não substitui autenticação.

## Exemplo de Agent Setup

### Papel do agente

Um agente de triagem interna que:

1. identifica o funcionário
2. classifica a solicitação
3. consulta prioridade
4. identifica o time responsável
5. cria o ticket

### Tools ativas

```text
get_employee
get_team
check_priority
create_ticket
```

### System prompt de exemplo

```text
Você é um agente de triagem da FlowDesk Lab.

Sua função é analisar a solicitação do usuário e, quando necessário:
1. identificar o funcionário pelo employee_id
2. classificar a categoria entre: it, hr, finance, facilities, security, other
3. estimar impact e urgency entre: low, medium, high
4. consultar a tool de prioridade
5. consultar a tool do time responsável
6. criar um ticket somente quando houver dados suficientes

Regras:
- não invente employee_id
- não invente categorias fora da lista
- se a solicitação estiver ambígua, use other
- explique resumidamente a decisão tomada
- sempre preserve um resumo curto e uma descrição clara para o ticket
```

## Exemplo de fluxo de uso do Agent

### Input do usuário

```text
Employee EMP001: não consigo entrar na VPN e preciso resolver isso ainda hoje.
```

### Passos esperados do agente

1. chamar `get_employee` com `EMP001`
2. inferir `category = it`
3. inferir `impact = medium` e `urgency = high` como resultado pedagógico esperado
4. chamar `check_priority`
5. chamar `get_team`
6. chamar `create_ticket`
7. responder com ticket, prioridade e time

## Exemplo de payload para `create_ticket`

```json
{
  "employee_id": "EMP001",
  "category": "it",
  "impact": "medium",
  "urgency": "high",
  "summary": "Falha de acesso à VPN",
  "description": "Funcionário relata impossibilidade de acesso à VPN e necessidade de continuidade do trabalho.",
  "source": "dify"
}
```

## Workflow Mode vs Agent Mode

| Critério | Workflow Mode | Agent Mode |
|----------|---------------|------------|
| Controle do fluxo | Alto | Médio |
| Determinismo | Alto | Menor |
| Tool calling autônomo | Limitado ao desenho | Natural |
| Melhor para aula inicial | Sim | Sim, após entender o contrato |
| Melhor para experimentos com LLM | Bom | Excelente |

## Quando usar Workflow Mode

Use quando você quiser:

- passos fixos
- roteamento previsível
- validação antes da criação do ticket
- demonstrações mais controladas

## Quando usar Agent Mode

Use quando você quiser:

- experimentar tool calling
- comparar raciocínio livre vs fluxo rígido
- testar ambiguidade, clarificação e fallback

## Dicas de laboratório

- comece importando apenas quatro tools
- valide os nomes dos campos antes de liberar `create_ticket`
- use prompts que forcem categorias válidas
- mantenha `X-Student-ID` consistente por turma ou grupo
