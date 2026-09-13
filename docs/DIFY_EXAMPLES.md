# Integração Dify - Quantum Commerce API

O Dify permite criar agentes inteligentes que usam a Quantum Commerce API como ferramentas (tools) para resolver problemas de clientes em tempo real.

## Configuração de Ferramentas (Tools)

Para adicionar a API ao Dify:
1. Vá em **Tools** > **Custom Tools** > **Create Custom Tool**.
2. No campo **Schema**, cole o conteúdo do arquivo `http://localhost:8000/openapi.json`.
3. Em **Authentication**, selecione `None` (o controle é feito via headers).
4. Adicione o header global `X-Lab-Group` com o valor do seu grupo (ex: `aluno-01`).

## Exemplo de Workflow de Agente: Suporte ao Cliente

Um agente de suporte pode seguir este fluxo lógico:

1. **Identificação**: O usuário informa o ID do cliente e o problema.
2. **Contexto**: O agente usa a ferramenta `get_customer_context` para verificar o perfil do cliente.
3. **Elegibilidade**: Se o usuário quer devolver um produto, o agente chama `check_return_eligibility`.
4. **Ação**: Se for elegível, o agente chama `create_return`. Se não for, explica o motivo baseado na política retornada.

## Boas Práticas

### Idempotência
Ao configurar a ferramenta `create_return` ou `create_support_case`, instrua o modelo a gerar um valor único para o header `Idempotency-Key`. No Dify, você pode usar variáveis de sistema ou pedir para o LLM gerar um hash baseado no `order_id` e `timestamp`.

### Headers Obrigatórios
Sempre inclua o header `X-Lab-Group`. Sem ele, seus dados serão misturados com o grupo `anonymous`.

## Exemplos de Prompts

### Prompt para Agente de Devoluções
> "Você é um assistente de suporte da Quantum Commerce. Sua tarefa é ajudar clientes com devoluções. 
> 1. Peça o ID do cliente e o ID do pedido.
> 2. Verifique a elegibilidade da devolução usando a ferramenta `check_return_eligibility`.
> 3. Se elegível, pergunte o motivo e use a ferramenta `create_return` para registrar a solicitação.
> 4. Se não for elegível, explique educadamente o motivo (ex: fora do prazo de 30 dias)."

### Prompt para Agente de Vendas e Promoções
> "Você é um consultor de compras. Use a ferramenta `get_eligible_promotions` para encontrar descontos personalizados para o cliente. 
> Se o cliente perguntar sobre um notebook, verifique o estoque usando `get_inventory_availability` informando o CEP do cliente."

## Tratamento de Erros no Dify

Se a API retornar um erro (ex: 404 ou 400), o Dify passará a mensagem de erro para o LLM. Configure o agente para:
- Não inventar dados se a ferramenta falhar.
- Pedir clarificação se o ID do cliente não for encontrado.
- Informar que reembolsos altos (acima de R$ 500) levam mais tempo pois dependem de aprovação humana.
