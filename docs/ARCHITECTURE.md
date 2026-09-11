# Architecture: FIAP Student Desk Lab

## System Flow

```mermaid
graph TD
    Student[Student] --> Webhook[Webhook]
    Webhook --> Workflow[n8n / Make / Dify]
    Workflow --> LLM[LLM - Cognition]
    LLM --> Knowledge[Knowledge Base]
    LLM --> StudentDeskAPI[Student Desk API - Execution]
    StudentDeskAPI --> DB[(SQLite Database)]
    Workflow --> Response[Response to Student]
```

## Human-in-the-Loop Flow (Aprovações)

```mermaid
graph TD
    Request[Academic Request] --> Critical{Needs Approval?}
    Critical -->|No| AutoProcessed[Auto-Processed]
    Critical -->|Yes| Pending[Pending Approval]
    Pending --> Human[Human Reviewer]
    Human -->|Approve| Approved[Approved]
    Human -->|Reject| Rejected[Rejected]
    Approved --> Audit[Audit Log]
    Rejected --> Audit
```

## Priority Matrix

```mermaid
graph LR
    I[Impact] --> P{Priority Calc}
    U[Urgency] --> P
    C[Category] --> P
    P --> Low[Low - 24h]
    P --> Medium[Medium - 8h]
    P --> High[High - 4h]
    P --> Critical[Critical - 1h]
```

## Notas Arquiteturais

- **Separação de Responsabilidades:** O LLM cuida da cognição (entendimento e geração), enquanto a API cuida da execução (dados e persistência).
- **Base de Conhecimento (RAG):** A API fornece endpoints de busca semântica para alimentar o contexto do LLM.
- **Isolamento Didático:** O header `X-Student-ID` permite que múltiplos grupos usem a mesma API sem misturar dados.
- **Resiliência:** A arquitetura prevê o tratamento de falhas simuladas (timeout, 500, 429) nos workflows.
- **Auditoria:** Todas as interações e decisões são registradas no endpoint `/api/v1/events`.

## Endpoints Principais
- **Students:** Dados cadastrais dos alunos.
- **Knowledge:** Artigos de ajuda e busca.
- **Requests:** Gestão de solicitações acadêmicas.
- **Interactions:** Registro de conversas com o assistente.
- **Approval:** Fluxo de decisão humana.
- **Lab:** Simuladores de falhas para testes de robustez.
