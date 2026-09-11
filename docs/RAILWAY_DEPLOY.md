# Deploy no Railway

## Objetivo

Publicar a FlowDesk Lab API em um ambiente acessível por URL pública para uso em n8n, Make, Dify, Postman e agentes.

## Passo a passo

### 1. Acessar o Railway

Abra: [https://railway.app](https://railway.app)

### 2. Criar um novo projeto

Clique em **New Project**.

### 3. Escolher deploy via GitHub

Selecione **Deploy from GitHub Repo**.

### 4. Escolher o repositório

Selecione o repositório onde está o projeto `tool_automation_lab`.

### 5. Deixar o Railway detectar o Dockerfile

O projeto já possui `api/Dockerfile`.

Se a detecção automática não funcionar:

- ajuste o diretório raiz do serviço para `api/`, ou
- configure o serviço manualmente para usar o Dockerfile dessa pasta.

### 6. Configurar variáveis de ambiente (opcional)

Para este laboratório, normalmente o deploy funciona com os defaults da aplicação.

Exemplos de variáveis úteis:

```env
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ORIGINS=https://SEU-FRONTEND.example.com
```

Não publique segredos reais no repositório.

> `X-Student-ID` não é autenticação. Se você publicar a API em domínio público, mantenha o uso estritamente didático e não conecte dados, credenciais ou integrações reais.

### 7. Verificar os logs de build

Na tela do serviço, acompanhe:

- instalação das dependências
- build da imagem
- comando de start
- eventuais erros de import, porta ou Docker context

### 8. Gerar um domínio público

Após o deploy, abra a aba de rede/domínio do Railway e gere um domínio público.

Exemplo:

```text
https://flowdesk-lab-api-production.up.railway.app
```

### 9. Testar o health check

Se a instância publicada expuser esse endpoint, abra no navegador ou use `curl`:

```bash
curl https://SEU-DOMINIO/health
```

Resposta esperada:

```json
{
  "status": "ok",
  "service": "flowdesk-lab-api",
  "version": "1.0.0"
}
```

### 10. Testar o Swagger

Abra:

```text
https://SEU-DOMINIO/docs
```

### 11. Testar o OpenAPI

Abra:

```text
https://SEU-DOMINIO/openapi.json
```

Esse endpoint é útil para importar a API como ferramenta em Dify ou para gerar coleções em outras plataformas.
Antes de depender dele em automações, confirme se o contrato publicado contém as operações esperadas.

## Checklist pós-deploy

- `GET /docs` abre a interface Swagger
- `GET /openapi.json` retorna o contrato JSON esperado
- se disponível na instância, `GET /health` responde `200`
- se disponível na instância, `GET /api/v1/employees/EMP001` responde corretamente
- se disponível na instância, `POST /api/v1/priority/check` aceita JSON

## Troubleshooting

### Build falhou

Verifique:

- se o Railway está apontando para a pasta correta
- se o `Dockerfile` usado é o de `api/`
- se `requirements.txt` e `requirements-dev.txt` existem no contexto esperado

### Erro de porta

Em PaaS, a aplicação normalmente precisa ouvir em `0.0.0.0` e na porta definida pela plataforma.
Se você migrar para start manual, use algo como:

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
```

### `/health` responde, mas `/docs` não abre

Verifique:

- se a aplicação FastAPI iniciou completamente
- se houve erro na carga de rotas durante o boot
- se o deploy publicado é a versão correta do serviço

### `openapi.json` não carrega

Cheque:

- erros de importação no startup
- logs da aplicação
- status code retornado pelo endpoint

### CORS em testes com front-end ou workflow remoto

Se necessário, ajuste:

```env
CORS_ORIGINS=https://SEU-FRONTEND.example.com
```

Em laboratório local, `*` pode ser útil temporariamente para troubleshooting, mas não é a opção recomendada para publicação pública.

### Banco SQLite e persistência

Como o projeto usa SQLite, o comportamento de persistência pode variar conforme a estratégia do ambiente.
Para laboratório, isso costuma ser suficiente; para produção real, prefira banco gerenciado.

## Sugestão de smoke tests

```bash
curl https://SEU-DOMINIO/
curl https://SEU-DOMINIO/health
curl https://SEU-DOMINIO/api/v1/employees/EMP001
curl -X POST https://SEU-DOMINIO/api/v1/priority/check \
  -H "Content-Type: application/json" \
  -H "X-Student-ID: grupo-07" \
  -d '{"employee_id":"EMP001","category":"it","impact":"medium","urgency":"high"}'
```

Se algum desses endpoints não aparecer no contrato publicado, trate isso como diferença entre o contrato esperado e a instância efetivamente executada.
