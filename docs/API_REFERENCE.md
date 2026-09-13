# Referência da API: Quantum Commerce

Esta documentação detalha os endpoints disponíveis na Quantum Commerce API, incluindo parâmetros, payloads e exemplos de resposta.

## Informações Gerais

- **Base URL:** `http://localhost:8000/api/v1`
- **Versão:** `2.0.0`
- **Formato de Dados:** JSON (UTF-8)
- **Headers Comuns:**
  - `X-Lab-Group`: Identificador do grupo para isolamento de dados (Default: `anonymous`).
  - `X-Request-ID`: Identificador único da requisição (ecoado na resposta).
  - `Idempotency-Key`: Chave para garantir que operações de escrita não sejam duplicadas.

## Formato de Erro

Em caso de erro, a API retorna o seguinte formato:
```json
{
  "detail": "Mensagem descritiva do erro"
}
```

---

## 1. Meta & Health

### GET `/`
Informações básicas do serviço.

### GET `/health`
Verificação de saúde do sistema.
**Resposta:** `{"status": "ok", "service": "quantum-commerce-api", "version": "2.0.0"}`

### GET `/api/v1/meta`
Metadados do sistema e contagem de entidades populadas.
**Exemplo de Resposta:**
```json
{
  "service": "Quantum Commerce API",
  "version": "2.0.0",
  "seeded_entities": {
    "customers": 50,
    "products": 171,
    "orders": 91
  }
}
```

---

## 2. Customers (Clientes)

### GET `/api/v1/customers/search`
Busca clientes por nome ou email.
- **Query Params:** `name`, `email`
- **Exemplo:** `/api/v1/customers/search?name=Marina`

### GET `/api/v1/customers/{id}`
Retorna os dados cadastrais de um cliente.
- **Exemplo:** `CUS-1001` (Marina Oliveira)

### GET `/api/v1/customers/{id}/context`
Retorna o contexto operacional do cliente (pedidos abertos, casos de suporte, etc).
**Exemplo de Resposta:**
```json
{
  "customer_id": "CUS-1001",
  "segment": "premium",
  "loyalty_tier": "gold",
  "total_orders": 47,
  "open_orders": 2,
  "open_support_cases": 1,
  "returns_last_12_months": 3,
  "lifetime_value": 18450.90
}
```

---

## 3. Catalog & Inventory (Catálogo e Estoque)

### GET `/api/v1/products/search`
Busca produtos no catálogo.
- **Query Params:** `q`, `category`, `brand`, `min_price`, `max_price`

### GET `/api/v1/products/{sku}`
Detalhes de um produto específico.
- **Exemplo:** `QTM-NBK-00123` (Notebook QuantumBook Pro 14)

### GET `/api/v1/inventory/{sku}`
Consulta a disponibilidade de estoque em todos os armazéns.
**Exemplo de Resposta:**
```json
{
  "sku": "QTM-NBK-00123",
  "total_available": 37,
  "warehouses": [
    {"warehouse_id": "BR-SP-01", "city": "São Paulo", "available": 21, "reserved": 4},
    {"warehouse_id": "BR-RJ-01", "city": "Rio de Janeiro", "available": 16, "reserved": 2}
  ]
}
```

---

## 4. Orders & Logistics (Pedidos e Logística)

### GET `/api/v1/orders/{id}`
Detalhes de um pedido, incluindo itens e status.
- **Exemplo:** `ORD-2026-10001`

### GET `/api/v1/orders/{id}/shipment`
Dados de envio vinculados ao pedido.
**Exemplo de Resposta:**
```json
{
  "order_id": "ORD-2026-10001",
  "shipment_id": "SHP-87421",
  "carrier": "Quantum Logistics",
  "status": "in_transit",
  "tracking_code": "QTM982734BR",
  "estimated_delivery": "2026-09-14",
  "events": [
    {"timestamp": "2026-09-12T22:15:00Z", "location": "Hub de São Paulo", "status": "in_transit", "description": "Em trânsito"}
  ]
}
```

---

## 5. Returns (Devoluções)

### POST `/api/v1/returns/check-eligibility`
Verifica se um produto de um pedido é elegível para devolução.
**Payload:** `{"order_id": "ORD-2026-10005", "sku": "QTM-AUD-01023"}`
**Resposta:**
```json
{
  "eligible": true,
  "reason": "within_return_window",
  "days_since_delivery": 12,
  "return_window_days": 30,
  "policy_id": "POL-RETURN-001"
}
```

### POST `/api/v1/returns`
Cria uma solicitação de devolução. **Requer Idempotency-Key.**
**Payload:** `{"customer_id": "CUS-1001", "order_id": "ORD-2026-10005", "sku": "QTM-AUD-01023", "reason": "Defeito"}`

---

## 6. Support (Suporte)

### POST `/api/v1/support/priority/check`
Calcula a prioridade de um caso com base no impacto e urgência.
**Payload:** `{"category": "delivery", "impact": "high", "urgency": "high"}`
**Resposta:** `{"priority": "P1", "sla_hours": 2}`

### POST `/api/v1/support/cases`
Abre um novo caso de suporte. **Requer Idempotency-Key.**

---

## 7. Approvals & Refunds (Aprovações e Reembolsos)

### POST `/api/v1/approvals`
Solicita uma aprovação manual.
**Payload:** `{"type": "refund", "reference_id": "ORD-2026-10001", "amount": 7499.90, "reason": "Valor alto"}`

### POST `/api/v1/refunds`
Processa um reembolso. Se o valor for superior a R$ 500,00, exige um `approval_id` com status `approved`.
**Payload:** `{"order_id": "ORD-2026-10001", "amount": 7499.90, "reason": "Atraso crítico", "approval_id": "APR-1002"}`

---

## 8. Lab (Didática)

Endpoints para simulação de cenários adversos:
- `GET /api/v1/lab/slow?seconds=5`: Simula latência.
- `GET /api/v1/lab/error`: Retorna erro 500.
- `GET /api/v1/lab/rate-limit`: Retorna 429 após 3 requisições/min por grupo.
- `GET /api/v1/lab/not-found`: Retorna 404.
- `POST /api/v1/lab/validation`: Valida schema e retorna 422 se inválido.
