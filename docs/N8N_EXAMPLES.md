# Exemplos n8n - Quantum Commerce API

Integre a Quantum Commerce API em seus fluxos do n8n usando o nó HTTP Request. Sempre configure o header `X-Lab-Group` com o identificador do seu grupo.

## 1. Consulta de Cliente e Contexto via Webhook

Este fluxo recebe um ID de cliente via Webhook e busca dados completos para tomada de decisão.

**Passos:**
1. **Webhook Node**: Método POST, path `customer-lookup`.
2. **HTTP Request Node (Get Customer)**:
   - Method: `GET`
   - URL: `http://localhost:8000/api/v1/customers/{{ $json.body.customer_id }}`
   - Headers:
     - `X-Lab-Group`: `aluno-XX`
3. **HTTP Request Node (Get Context)**:
   - Method: `GET`
   - URL: `http://localhost:8000/api/v1/customers/{{ $json.id }}/context`
   - Headers:
     - `X-Lab-Group`: `aluno-XX`

## 2. Devolução Idempotente com Verificação de Elegibilidade

Fluxo para validar se um produto pode ser devolvido antes de criar o registro.

**Passos:**
1. **HTTP Request (Check Eligibility)**:
   - Method: `POST`
   - URL: `http://localhost:8000/api/v1/returns/check-eligibility`
   - Body:
     ```json
     {
       "order_id": "ORD-2026-10005",
       "sku": "QTM-AUD-01023"
     }
     ```
2. **If Node**: Verifica se `eligible` é `true`.
3. **Code Node (Generate UUID)**:
   - Gera um UUID para a chave de idempotência.
   ```javascript
   $json.idempotency_key = crypto.randomUUID();
   return $json;
   ```
4. **HTTP Request (Create Return)**:
   - Method: `POST`
   - URL: `http://localhost:8000/api/v1/returns`
   - Headers:
     - `Idempotency-Key`: `{{ $json.idempotency_key }}`
   - Body:
     ```json
     {
       "customer_id": "CUS-1001",
       "order_id": "ORD-2026-10005",
       "sku": "QTM-AUD-01023",
       "reason": "Arrependimento"
     }
     ```

## 3. Reembolso com Aprovação Humana (Human-in-the-Loop)

Fluxo para reembolsos acima de R$ 500 que exigem aprovação manual.

**Passos:**
1. **HTTP Request (Create Approval)**:
   - Method: `POST`
   - URL: `http://localhost:8000/api/v1/approvals`
   - Body:
     ```json
     {
       "type": "refund",
       "reference_id": "ORD-2026-10001",
       "amount": 7499.90,
       "reason": "Atraso crítico na entrega",
       "requested_by": "n8n-workflow"
     }
     ```
2. **Wait Node**: Aguarda um tempo ou usa um Webhook de callback para a decisão humana.
3. **HTTP Request (Check Approval Status)**:
   - Consulta `GET /api/v1/approvals/{{ $json.approval_id }}` até que o status seja `approved`.
4. **HTTP Request (Process Refund)**:
   - Method: `POST`
   - URL: `http://localhost:8000/api/v1/refunds`
   - Body:
     ```json
     {
       "order_id": "ORD-2026-10001",
       "amount": 7499.90,
       "reason": "delivery_issue",
       "approval_id": "APR-XXXXX"
     }
     ```

## 4. Promoções Elegíveis e Notificação

Busca promoções para um cliente e filtra apenas as que ele pode usar.

**Passos:**
1. **HTTP Request (Get Eligible Promos)**:
   - Method: `GET`
   - URL: `http://localhost:8000/api/v1/promotions/eligible`
   - Query Params:
     - `customer_id`: `CUS-1001`
     - `sku`: `QTM-NBK-00123`
2. **Item Lists Node**: Filtra a lista onde `eligible` é `true`.
3. **HTTP Request (Simulate Notification)**:
   - Envia os dados da promoção para um serviço de mensageria ou registra uma interação via `POST /api/v1/interactions`.

## 5. Monitoramento de Rate Limit com Retry

Exemplo de como lidar com o erro 429 (Too Many Requests) usando as configurações do nó HTTP Request.

**Configuração do Nó HTTP Request:**
- **Error Handling**: Marque "Retry on Failure".
- **Number of Retries**: 3.
- **Delay Between Retries**: 10000 (ms).
- **URL**: `http://localhost:8000/api/v1/lab/rate-limit`.

**Lógica:**
O n8n tentará a chamada novamente se receber um erro 429. No laboratório, o rate limit é de 3 requisições por minuto. A quarta chamada falhará, disparando o retry automático.

## Dicas de Configuração

- **Base URL**: Use variáveis de ambiente para alternar entre `localhost:8000` e a URL do Railway.
- **Headers Globais**: Use o nó "Set" no início do fluxo para definir o `X-Lab-Group` e reutilize-o em todos os nós HTTP.
- **JSON**: Certifique-se de que a opção "JSON/Raw Parameters" está ativa ao enviar corpos de requisição POST.
