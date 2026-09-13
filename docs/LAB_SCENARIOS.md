# Cenários de Laboratório - Quantum Commerce API

Este documento descreve 15 cenários didáticos para explorar as funcionalidades da Quantum Commerce API. Use o header `X-Lab-Group: aluno-XX` para isolar seus dados.

## S1 Conexão e observabilidade

Objetivo: Verificar se a API está ativa e entender os metadados do ambiente.

Endpoints:
- `GET /health`
- `GET /api/v1/health`
- `GET /api/v1/meta`

Exemplo:
```bash
curl -H "X-Lab-Group: aluno-01" http://localhost:8000/api/v1/meta
```

Saída esperada:
JSON com versão 2.0.0, data determinística 2026-09-13 e contagem de entidades semeadas.

O que observar:
A API retorna headers como `X-Request-ID`. O campo `seed_today` confirma que o tempo no laboratório é fixo.

## S2 Consulta de cliente e contexto

Objetivo: Obter dados detalhados de um cliente e seu contexto operacional live.

Endpoints:
- `GET /api/v1/customers/CUS-1001`
- `GET /api/v1/customers/CUS-1001/context`

Exemplo:
```bash
curl -H "X-Lab-Group: aluno-01" http://localhost:8000/api/v1/customers/CUS-1001/context
```

Saída esperada:
Dados de Marina Oliveira, incluindo `open_orders`, `returns_last_12_months` e `lifetime_value`.

O que observar:
O endpoint `/context` computa valores em tempo real baseados no estado atual do banco de dados.

## S3 Catálogo e busca de produtos

Objetivo: Explorar o catálogo de produtos com filtros de busca.

Endpoints:
- `GET /api/v1/products/QTM-NBK-00123`
- `GET /api/v1/products/search?q=QuantumBook&min_price=5000`

Exemplo:
```bash
curl -H "X-Lab-Group: aluno-01" "http://localhost:8000/api/v1/products/search?q=QuantumBook&category=electronics"
```

Saída esperada:
Lista de notebooks da linha QuantumBook.

O que observar:
Os filtros são cumulativos. O SKU `QTM-NBK-00123` refere-se ao QuantumBook Pro 14.

## S4 Estoque e disponibilidade por região

Objetivo: Verificar níveis de estoque e prazos de entrega baseados no CEP.

Endpoints:
- `GET /api/v1/inventory/QTM-NBK-00123`
- `GET /api/v1/inventory/QTM-NBK-00123/availability?postal_code=01310-100`

Exemplo:
```bash
curl -H "X-Lab-Group: aluno-01" "http://localhost:8000/api/v1/inventory/QTM-NBK-00123/availability?postal_code=01310-100"
```

Saída esperada:
`available: true`, `quantity: 21`, `estimated_delivery_days: 2`.

O que observar:
O primeiro dígito do CEP define o armazém. CEPs começando com 0 mapeiam para BR-SP-01. O produto `QTM-NBK-00150` está sem estoque.

## S5 Pedido e rastreamento logístico

Objetivo: Consultar detalhes de um pedido e o histórico de eventos de entrega.

Endpoints:
- `GET /api/v1/orders/ORD-2026-10001`
- `GET /api/v1/orders/ORD-2026-10001/shipment`

Exemplo:
```bash
curl -H "X-Lab-Group: aluno-01" http://localhost:8000/api/v1/orders/ORD-2026-10001/shipment
```

Saída esperada:
Dados da transportadora Quantum Logistics e lista de eventos com timestamps.

O que observar:
O pedido `ORD-2026-10001` está em trânsito. Verifique o código de rastreio `QTM982734BR`.

## S6 Políticas de negócio

Objetivo: Consultar regras de devolução e cancelamento.

Endpoints:
- `GET /api/v1/policies?category=returns&country=BR`
- `GET /api/v1/policies/search?q=devolução`

Exemplo:
```bash
curl -H "X-Lab-Group: aluno-01" http://localhost:8000/api/v1/policies/POL-RETURN-001
```

Saída esperada:
Texto da política de devolução padrão para o Brasil.

O que observar:
As políticas são usadas para alimentar bases de conhecimento de agentes de IA.

## S7 Elegibilidade de devolução (Dentro do prazo)

Objetivo: Validar se um item pode ser devolvido seguindo as regras de negócio.

Endpoint:
- `POST /api/v1/returns/check-eligibility`

Payload:
```json
{
  "order_id": "ORD-2026-10005",
  "sku": "QTM-AUD-01023"
}
```

Saída esperada:
`eligible: true`. O pedido foi entregue há 12 dias, dentro da janela de 30 dias.

O que observar:
A API calcula a diferença entre a data atual (2026-09-13) e a data de entrega no histórico logístico.

## S8 Elegibilidade de devolução (Fora do prazo)

Objetivo: Testar a rejeição automática de devoluções fora da janela permitida.

Endpoint:
- `POST /api/v1/returns/check-eligibility`

Payload:
```json
{
  "order_id": "ORD-2026-10007",
  "sku": "QTM-BED-01089"
}
```

Saída esperada:
`eligible: false`, `reason: "outside_return_window"`.

O que observar:
Este pedido foi entregue há 50 dias. A janela para o Brasil é de 30 dias.

## S9 Criação de devolução idempotente

Objetivo: Criar uma solicitação de devolução garantindo que duplicatas não ocorram.

Endpoint:
- `POST /api/v1/returns`

Header:
`Idempotency-Key: unique-uuid-123`

Payload:
```json
{
  "customer_id": "CUS-1001",
  "order_id": "ORD-2026-10005",
  "sku": "QTM-AUD-01023",
  "reason": "Produto incompatível"
}
```

Saída esperada:
201 Created na primeira chamada. 200 OK com o mesmo corpo nas chamadas subsequentes com a mesma chave.

O que observar:
O protocolo gerado segue o padrão `QRET-2026-XXXXX`.

## S10 Suporte e classificação de prioridade

Objetivo: Verificar a prioridade de um caso e criar um ticket de suporte.

Endpoints:
- `POST /api/v1/support/priority/check`
- `POST /api/v1/support/cases`

Exemplo de prioridade:
```json
{
  "category": "delivery",
  "impact": "high",
  "urgency": "high"
}
```

Saída esperada:
`priority: P1`, `sla_hours: 2`.

O que observar:
A matriz de prioridade define o SLA. P1 exige impacto e urgência altos.

## S11 Aprovação humana e reembolso de alto valor

Objetivo: Fluxo de reembolso que exige aprovação manual para valores acima de R$ 500.

Endpoints:
- `POST /api/v1/approvals`
- `POST /api/v1/approvals/{id}/decision`
- `POST /api/v1/refunds`

Fluxo:
1. Tente criar reembolso de R$ 7499.90 sem aprovação (Erro 400).
2. Crie solicitação de aprovação.
3. Aprove a solicitação via endpoint de decisão.
4. Crie o reembolso enviando o `approval_id`.

O que observar:
O sistema bloqueia reembolsos altos sem o token de aprovação de um supervisor.

## S12 Promoções e elegibilidade

Objetivo: Consultar promoções ativas e verificar se um cliente/produto é elegível.

Endpoints:
- `GET /api/v1/promotions?country=BR`
- `GET /api/v1/promotions/eligible?customer_id=CUS-1001&sku=QTM-NBK-00123`

Saída esperada:
Lista de promoções com campo `eligible` e `reason` em caso de negação.

O que observar:
A promoção `PROMO-101` (Fashion Friday) falhará para notebooks com `reason: category_mismatch`.

## S13 Registro de interações

Objetivo: Manter o histórico de conversas entre o cliente e agentes (IA ou humanos).

Endpoints:
- `POST /api/v1/interactions`
- `GET /api/v1/interactions?customer_id=CUS-1001`

Payload:
```json
{
  "customer_id": "CUS-1001",
  "channel": "whatsapp",
  "message": "Como faço para rastrear meu pedido?",
  "response": "Você pode usar o endpoint de shipment com o ID ORD-2026-10001.",
  "source": "ai-agent"
}
```

O que observar:
As interações ajudam a manter o contexto em fluxos multi-turno.

## S14 Auditoria e simulação de falhas (Lab)

Objetivo: Testar resiliência e observar logs de eventos.

Endpoints:
- `GET /api/v1/events?type=customer_lookup`
- `GET /api/v1/lab/rate-limit`
- `GET /api/v1/lab/slow?seconds=10`

O que observar:
O endpoint de rate-limit bloqueia após 3 chamadas no mesmo minuto (Erro 429). O endpoint slow testa timeouts de integração.

## S15 Tratamento de erros comuns

Objetivo: Identificar e tratar códigos de status HTTP corretamente.

Cenários:
- 404: `GET /api/v1/customers/CUS-9999` (Não encontrado)
- 422: `POST /api/v1/lab/validation` com body inválido (Erro de esquema)
- 409: `POST /api/v1/returns` com Idempotency-Key já usada para outro recurso (Conflito)
- 400: `POST /api/v1/refunds` sem aprovação necessária (Regra de negócio)

O que observar:
A API segue padrões RESTful. Erros de validação detalham quais campos falharam.
