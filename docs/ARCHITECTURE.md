# Architecture

## System Flow

```mermaid
graph TD
    User[User] --> Webhook[Webhook]
    Webhook --> Workflow[n8n / Make / Dify]
    Workflow --> LLM[LLM - Classification]
    LLM --> FlowDesk[FlowDesk API]
    FlowDesk --> DB[(SQLite Database)]
    Workflow --> Response[Response to User]
```

## Human-in-the-Loop Flow

```mermaid
graph TD
    Request[Access Request] --> Check{Risk = low?}
    Check -->|Yes| AutoApproved[Auto-Approved]
    Check -->|No| Pending[Pending Approval]
    Pending --> Human[Human Review]
    Human -->|Approve| Approved[Approved]
    Human -->|Reject| Rejected[Rejected]
```

## Priority Matrix

```mermaid
graph LR
    I[Impact] --> P{Priority Calc}
    U[Urgency] --> P
    C[Category] --> P
    P --> Low[Low - 12h a 24h]
    P --> Medium[Medium - 6h a 8h]
    P --> High[High - 2h a 4h]
    P --> Critical[Critical - 1h]
```

## Notas arquiteturais

- a API expõe endpoints REST simples para consumo por workflows e agentes
- o banco usado no laboratório é SQLite
- `X-Student-ID` funciona como contexto didático entre grupos
- a rota de prioridade usa regra determinística baseada em `impact`, `urgency` e override para `security`
- apenas `risk = low` segue autoaprovação; `medium` e `high` passam por `pending_approval`
- as rotas `lab/*` existem para exercícios de timeout, erro, rate limit e validação
