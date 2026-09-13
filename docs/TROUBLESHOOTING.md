# Solução de Problemas - Quantum Commerce API

Guia para resolver os erros mais comuns ao usar a API em laboratórios.

## Erros de Requisição (HTTP 4xx)

### 404 Not Found em /customers/search
Se você receber 404 ao tentar buscar um cliente, verifique se a URL está correta. Na Quantum API, a rota `/api/v1/customers/search` está definida antes da rota `/api/v1/customers/{id}`, portanto o sistema identifica corretamente a busca. Se o erro persistir, verifique se o cliente realmente existe no banco de dados usando o ID direto.

### 400 Bad Request em Reembolsos
O erro "Refunds above R$500.00 require an approved approval" ocorre quando você tenta criar um reembolso de alto valor sem um `approval_id` válido e aprovado. 
**Solução**: Crie primeiro uma solicitação de aprovação, registre a decisão como `approved` e então use o ID gerado no corpo do reembolso.

### 409 Conflict (Idempotency)
Ocorre em dois casos:
1. Você enviou a mesma `Idempotency-Key` para dois recursos diferentes (ex: usou a mesma chave para criar um retorno e depois um caso de suporte).
2. Você tentou registrar uma decisão em uma aprovação que já foi finalizada.
**Solução**: Use sempre UUIDs únicos para cada nova operação.

### 422 Unprocessable Entity
Indica que o corpo do JSON enviado não segue o esquema esperado (ex: falta um campo obrigatório ou o tipo de dado está errado).
**Solução**: Verifique o Swagger (`/docs`) para validar o formato exato do payload.

### 429 Too Many Requests
O endpoint `/api/v1/lab/rate-limit` permite apenas 3 requisições por minuto por grupo.
**Solução**: Aguarde 60 segundos ou altere o header `X-Lab-Group` para continuar os testes.

## Erros de Ambiente e Banco de Dados

### Database is locked (SQLite)
O SQLite pode travar se houver muitas conexões simultâneas escrevendo no arquivo.
**Solução**: Reinicie o servidor Uvicorn. Se estiver no Railway, o serviço reiniciará automaticamente.

### Erro de Seed Duplicado
Se ao rodar o script de seed você receber erros de integridade (Unique Constraint), significa que os dados já existem.
**Solução**: O script de seed da Quantum API é idempotente e ignora a execução se já houver dados. Para limpar tudo, use o script `reset_lab.py`.

### Problemas com venv no iCloud/OneDrive
Pastas sincronizadas em nuvem podem corromper o ambiente virtual Python.
**Solução**: Crie sua `venv` em uma pasta local fora da sincronização (ex: `C:\temp` ou `~/Documents/lab`).

## Integrações e Deploy

### CORS com n8n ou Navegador
Se o n8n (versão desktop) ou um frontend não conseguir acessar a API, verifique as configurações de CORS no arquivo `api/app/main.py`. A API está configurada para aceitar origens comuns de laboratório.

### Variáveis de Ambiente no Railway
Certifique-se de configurar a variável `DATABASE_URL` como `sqlite:///./quantum.db` se não estiver usando um banco externo. A variável `ENVIRONMENT` deve ser `production` para desativar logs excessivos.

## Scripts de Utilidade

### Como resetar o laboratório
Para apagar todos os dados e voltar ao estado inicial do seed:
```bash
python scripts/reset_lab.py
```
Este comando apaga o arquivo `quantum.db` e executa o seed novamente. Use com cautela, pois todos os registros criados pelos alunos (X-Lab-Group) serão perdidos.
