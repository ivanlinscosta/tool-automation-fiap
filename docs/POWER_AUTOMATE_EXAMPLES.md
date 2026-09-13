# Power Automate - Quantum Commerce API

Use o conector "HTTP" do Power Automate para integrar processos de negócio com a Quantum Commerce API.

## 1. Consulta de Pedido

Busca os detalhes de um pedido para enviar um e-mail de confirmação.

**Configuração:**
- **Método**: `GET`
- **URI**: `http://localhost:8000/api/v1/orders/ORD-2026-10001`
- **Headers**:
  - `X-Lab-Group`: `aluno-XX`

## 2. Verificação de Elegibilidade de Devolução

Valida se um processo de devolução pode ser iniciado.

**Configuração:**
- **Método**: `POST`
- **URI**: `http://localhost:8000/api/v1/returns/check-eligibility`
- **Body**:
  ```json
  {
    "order_id": "ORD-2026-10005",
    "sku": "QTM-AUD-01023"
  }
  ```

## 3. Criação de Caso de Suporte com Idempotência

Cria um ticket de suporte garantindo que falhas de rede não gerem tickets duplicados.

**Configuração:**
- **Método**: `POST`
- **URI**: `http://localhost:8000/api/v1/support/cases`
- **Headers**:
  - `Idempotency-Key`: `guid()` (Use a expressão dinâmica `guid()`)
  - `X-Lab-Group`: `aluno-XX`
- **Body**:
  ```json
  {
    "customer_id": "CUS-1001",
    "category": "delivery",
    "summary": "Atraso na entrega",
    "description": "O pedido ORD-2026-10001 não foi entregue no prazo."
  }
  ```

## 4. Fluxo de Reembolso com Aprovação

Integra a aprovação nativa do Power Automate com a API.

**Passos:**
1. **HTTP**: Cria solicitação de aprovação na API via `POST /api/v1/approvals`.
2. **Approvals (Conector Nativo)**: Envia um card de aprovação para o gerente no Teams/Outlook.
3. **Condition**: Se aprovado:
   - **HTTP**: Envia decisão para a API via `POST /api/v1/approvals/{id}/decision`.
   - **HTTP**: Cria o reembolso via `POST /api/v1/refunds` enviando o `approval_id`.

## 5. Tratamento de Rate Limit e Retry

O Power Automate possui uma política de repetição padrão. Para a Quantum API, configure:

**Configuração da Ação HTTP:**
- **Settings** > **Retry Policy**:
  - **Type**: `Fixed Interval`
  - **Count**: 3
  - **Interval**: `PT10S` (10 segundos)

Isso garante que, se a API retornar um erro 429 (Too Many Requests), o fluxo aguardará o tempo necessário antes de tentar novamente.

## Dicas de JSON

Ao usar a saída de uma ação HTTP em passos seguintes, use a ação **Parse JSON**.
- **Content**: Body da ação HTTP.
- **Schema**: Use a opção "Generate from sample" e cole um exemplo de resposta da documentação Swagger (`/docs`).
