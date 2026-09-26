# Guia de consumo da API em produção — 12 grupos

Referência única para consumir a **Quantum Commerce API** e os **12 laboratórios
de workflow** em produção. Cada grupo tem uma seção independente com contexto de
negócio, base URL, endpoints, variáveis e exemplos de GET e POST.

Todos os ids, enums e contagens deste documento foram extraídos do OpenAPI
e de um banco de dados local recém-semeado. Cada exemplo de POST e GET foi
executado e validado contra essa instância local.

| | |
|---|---|
| **Base URL (produção)** | `https://tool-automation-fiap-production.up.railway.app` |
| **Swagger (produção)** | `https://tool-automation-fiap-production.up.railway.app/docs` |
| **OpenAPI (produção)** | `https://tool-automation-fiap-production.up.railway.app/openapi.json` |
| **Healthcheck** | `GET /health` |
| **Prefixo dos labs** | `/api/v1/labs` |
| **Prefixo de cada grupo** | `/api/v1/labs/groups/{group_id}` |
| **Total de operações** | 169 (164 dos 12 grupos + 5 de plataforma) — código local e produção estão idênticos |

> **Contrato local e produção estão em sincronia.** As 169 operações de labs
> deste guia respondem em produção. O grupo 08 tem rota própria e rota
> compartilhada para os dois recursos, e ambas devolvem JSON idêntico:
> `unlock-stats` ≡ `stats` e `unlock-history` ≡ `history`. Prefira os paths
> próprios em código novo. Veja [Grupo 08](#grupo-08--desbloqueio-em-confiança).

---

## 0. Antes de começar

Esta seção vale para os 12 grupos. Cada grupo repete o essentials do que for
específico dele.

### 0.1 Base URL

```bash
export BASE=https://tool-automation-fiap-production.up.railway.app
```

Todos os exemplos daqui para frente usam `$BASE`.

### 0.2 Identificação do grupo

O `{group_id}` do path aceita três formatos equivalentes:

```
/api/v1/labs/groups/01/leads
/api/v1/labs/groups/1/leads
/api/v1/labs/groups/group-01/leads
```

### 0.3 Autenticação e headers

A API é pública por design, para uso em sala de aula. Não há token.

| Header | Obrigatório | Para quê |
|---|---|---|
| `X-Lab-Group` | não | Identifica a dupla/equipe no log de auditoria. Não controla acesso. Sem ele, o servidor registra `anonymous`. |
| `X-Instructor-Key` | só em rotas de instrutor | Revela a resposta correta do exercício. Hoje responde `403` porque `LABS_INSTRUCTOR_KEY` está vazia em produção. |
| `Idempotency-Key` | não | Só no grupo 03 e em 4 rotas da API original. Ver [0.7](#07-idempotência). |
| `Content-Type` | em POST | `application/json` |

```bash
curl -H "X-Lab-Group: grupo-alfa" "$BASE/api/v1/labs/groups/01/leads?limit=1"
```

### 0.4 Paginação

Toda listagem devolve o mesmo envelope:

```json
{
  "items": [],
  "meta": { "total": 1084, "limit": 20, "offset": 0, "total_pages": 55, "has_more": true }
}
```

- `limit`: 1 a 200, padrão 20
- `offset`: 0 ou maior, padrão 0
- `has_more`: use para parar, em vez de calcular a página final
- `sort` e `order` (`asc`/`desc`) em todas as listagens; `sort` inválido → `400`

```python
def iterar(base, grupo, recurso, headers):
    offset, limite = 0, 200
    while True:
        r = requests.get(
            f"{base}/api/v1/labs/groups/{grupo}/{recurso}",
            params={"limit": limite, "offset": offset},
            headers=headers, timeout=30,
        )
        r.raise_for_status()
        corpo = r.json()
        yield from corpo["items"]
        if not corpo["meta"]["has_more"]:
            return
        offset += limite
```

### 0.5 Injeção de falha (`?scenario=`)

Todo endpoint de lab aceita `?scenario=` para simular erros — é o material para
ensinar tratamento de erro.

| Valor | Comportamento |
|---|---|
| `success` | Executa normalmente (padrão) |
| `validation_error` | **422** — payload rejeitado |
| `not_found` | **404** — recurso inexistente |
| `duplicate` | **409** — já processado |
| `timeout` | dorme 5s, depois **504** |
| `server_error` | **500** — falha na dependência upstream |

```bash
curl -i "$BASE/api/v1/labs/groups/03/loads?scenario=timeout"
```

- `?scenario=` só existe nos endpoints de lab; a API original nunca falha assim.
- Valor desconhecido → **400** com a lista de valores suportados.
- Se `LABS_ALLOW_SCENARIOS=false`, todos devolvem **400**. Em produção está `true`.

### 0.6 Códigos de erro

| Código | Quando acontece | O que fazer |
|---|---|---|
| `400` | `sort` inválido, ou `scenario` desconhecido/desabilitado | Corrija o parâmetro |
| `401` | `X-Instructor-Key` ausente ou errada (só com chave configurada) | Envie a chave correta |
| `403` | Instrutor desabilitado (sem `LABS_INSTRUCTOR_KEY`) | Configure a variável |
| `404` | Grupo inexistente, registro não encontrado, ou rota chamada com o grupo errado | Confira o `{group_id}` |
| `409` | Recurso já processado (chave de negócio duplicada) | Trate como sucesso idempotente |
| `422` | Payload inválido, ou `?scenario=validation_error` | Valide antes de enviar |
| `500` | Falha interna, ou `?scenario=server_error` | Log e retry com backoff |
| `503` | Seed do grupo indisponível | Tente de novo em instantes |
| `504` | `?scenario=timeout` | Configure timeout do cliente acima de 5s |

O `404` de grupo errado é a defesa contra rota trocada: todo endpoint valida o
próprio grupo antes de devolver dados.

### 0.7 Idempotência

**API original** — header `Idempotency-Key` (opcional) honrado em 4 rotas:
`POST /api/v1/returns`, `/refunds`, `/approvals`, `/support/cases`. A primeira
chamada guarda o resultado; repetir a mesma chave devolve a resposta original em
vez de duplicar. Mesma chave com payload diferente → **409**. A chave é escopada
por `X-Lab-Group`.

**Laboratórios** — cada grupo garante idempotência pela própria regra do
exercício, exceto o grupo 03 que também aceita `Idempotency-Key`:

| Grupo | Endpoint | Regra |
|---|---|---|
| 01 | `POST /leads` | deduplica por e-mail + telefone; repetido → **409** `Duplicate lead detected` |
| 01 | `POST /leads/check-duplicates` | consulta a chave sem criar nada |
| 03 | `POST /loads` | aceita `Idempotency-Key` (opcional) e não repete os deals do CRM |
| 05 | `POST /tickets/{ticket_id}/respond` | um ticket aceita uma resposta; template diferente → **409** |
| 07 | `POST /receivables/{receivable_id}/send-collection` | idempotente no mesmo dia |
| 07 | `POST /process-retry` | reprocessa falhas sem duplicar histórico |
| 10 | `POST /patient-messages` | `wa_id` único; repetido → **409** `wa_id already exists` |
| 12 | `POST /submissions` | `modelo_id` único; repetido → **409** `modelo_id already exists` |

### 0.8 Seed sob demanda

`LABS_SEED_ON_STARTUP=false`, então **um grupo só é populado no primeiro
acesso**. Antes disso, `GET /api/v1/labs/groups` mostra `seeded: false` e
`total_records: 0` — não é erro, é o estado inicial. O primeiro `GET`/`POST` em
um grupo dispara o seed e pode demorar alguns segundos.

### 0.9 Variáveis de ambiente em produção

Não existem OVERRIDES de variáveis `LABS_*` configurados no Railway, portanto
os defaults do código listados na tabela abaixo se aplicam.

| Variável | Default | O que controla |
|---|---|---|
| `LABS_SEED` | `2026` | Semente fixa compartilhada por todos os geradores. Torna os dados reproduzíveis. |
| `LABS_TODAY` | `2026-09-13` | Data de referência para montar datasets temporalmente coerentes. |
| `LABS_MIN_RECORDS` | `1000` | Mínimo de registros na tabela principal de cada grupo. |
| `LABS_ALLOW_SCENARIOS` | `true` | Habilita a injeção de falhas via `?scenario=`. |
| `LABS_SCENARIO_TIMEOUT_SECONDS` | `5` | Quanto `?scenario=timeout` dorme antes de responder 504. |
| `LABS_SEED_ON_STARTUP` | `false` | Se `true`, semeia os 12 grupos no boot em vez de sob demanda. |
| `LABS_INSTRUCTOR_KEY` | `""` (vazio) | Chave dos endpoints de instrutor. **Vazio = desabilitados (403).** |

| Variável | Valor em produção | Efeito |
|---|---|---|
| `APP_NAME` | `Quantum Commerce API` | Nome exibido em `/api/v1/meta` |
| `ENVIRONMENT` | `development` ⚠️ | Deveria ser `production` |
| `DATABASE_URL` | `sqlite:///./quantum_commerce.db` ⚠️ | Banco SQLite no filesystem do container |
| `CORS_ORIGINS` | `*` | Libera qualquer origem |
| `LOG_LEVEL` | `INFO` | Nível dos logs |
| `VERSION` | `2.0.0` | Versão da API |
| `REFUND_APPROVAL_THRESHOLD` | `500.0` | Limite de aprovação manual de reembolso |
| `RETURN_WINDOW_DAYS` | `30` | Janela padrão de devolução |

O Railway também injeta `RAILWAY_ENVIRONMENT`, `RAILWAY_PUBLIC_DOMAIN`,
`RAILWAY_PRIVATE_DOMAIN`, `RAILWAY_PROJECT_ID`, `RAILWAY_SERVICE_ID` e afins.
Nenhuma é lida pelo código. A porta `PORT` é injetada em runtime e consumida
pelo Dockerfile.

**Três riscos de configuração que afetam turmas inteiras:**

1. **`ENVIRONMENT=development`** — a API serve produção com o flag de ambiente
   em `development`. Não quebra nada hoje porque nenhuma lógica do código faz
   branch em `ENVIRONMENT`, mas é enganoso em logs.
2. **`DATABASE_URL` em SQLite** — o Railway não persiste o filesystem do
   container sem volume montado. **A persistência do banco em produção não foi
   verificada**: confirme se existe volume antes de usar em atividade avaliada.
   Se não houver, todo redeploy apaga o progresso de aluno.
3. **`LABS_INSTRUCTOR_KEY` vazia** — os endpoints de instrutor respondem **403**,
   e não 401:
   `{"detail":"Instructor endpoints are disabled because LABS_INSTRUCTOR_KEY is not configured"}`
   Isso é intencional e seguro: sem a chave, o ground truth não é servido.

### 0.10 Checklist de consumo

```bash
export BASE=https://tool-automation-fiap-production.up.railway.app

# 1. serviço no ar
curl -s "$BASE/health"

# 2. convenções e cenários disponíveis
curl -s "$BASE/api/v1/labs/meta"

# 3. um grupo já semeado, primeira página
curl -s -H "X-Lab-Group: grupo-alfa" \
  "$BASE/api/v1/labs/groups/10/patient-messages?limit=2"

# 4. tratamento de erro
curl -s -i "$BASE/api/v1/labs/groups/10/patient-messages?scenario=duplicate"

# 5. quais grupos já estão semeados
curl -s "$BASE/api/v1/labs/groups"
```

---

# Grupo 01 — Prospecção e qualificação de leads

### Contexto de negócio

Uma equipe comercial captura leads de vários canais (site, indicação, evento,
LinkedIn, WhatsApp, e-mail marketing, parceiro, outbound), verifica se o contato
já existe, distribui o lead para um representante de vendas conforme região e
segmento, e qualifica o lead. A qualification final é feita por LLM — o
endpoint de instrutor revela o label real para você comparar com a sua
classificação.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/01
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `lead_id` | `LEAD-000001` (6 dígitos) |
| path | `{group_id}` | `01`, `1`, `group-01` |
| query | `status` | `NOVO`, `EM_QUALIFICACAO`, `CONVERTIDO`, `DESQUALIFICADO`, `DESCARTADO` |
| query | `origem` | `site`, `indicacao`, `evento`, `linkedin`, `whatsapp`, `email_marketing`, `parceiro`, `outbound` |
| query | `segmento` | `startup`, `small_business`, `mid_market`, `enterprise`, `public_sector`, `nonprofit` |
| query | `regiao` | `SP`, `MG`, `RJ`, `RS`, `PR`, `BA`, `CE`, `DF`, `ES`, `PE`, `RN` |
| query | `produto_interesse` | `PROD-01` a `PROD-12` |
| query | `responsavel` | id do representante, `SR-01` a `SR-14` |
| query | `search` | case-insensitive em `nome`, `empresa`, `email`, `mensagem` |
| query | `include_inactive` | em `/sales-reps`, padrão `true` |
| body `POST /leads` | `origem` **obrigatório** | os mesmos 8 valores de `origem` acima |
| body `POST /leads` | demais campos | `nome`, `empresa`, `email`, `telefone`, `segmento`, `regiao`, `produto_interesse`, `mensagem`, `created_at` — todos opcionais |
| body `POST /leads/{id}/status` | `status` **obrigatório** | os valores documentados são os do enum de `status` acima; o campo é uma string livre não validada contra o enum |
| body `POST /leads/{id}/status` | `motivo_desqualificacao`, `qualificado`, `last_contact_at` | opcionais |
| body `POST /leads/{id}/assign` | `responsavel` **obrigatório** | `SR-01` a `SR-14` |
| header | `X-Lab-Group` | identificação da dupla no log |

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/leads` | Listar leads com filtros, ordenação e paginação | não |
| `GET` | `/leads/{lead_id}` | Obter um lead por id | não |
| `POST` | `/leads` | Capturar lead com detecção de duplicidade | não |
| `POST` | `/leads/check-duplicates` | Verificar se o payload já existe | não |
| `POST` | `/leads/{lead_id}/assign` | Atribuir lead a um representante | não |
| `POST` | `/leads/{lead_id}/status` | Atualizar status e motivo de desqualificação | não |
| `GET` | `/campaigns` | Listar campanhas de aquisição | não |
| `GET` | `/sales-reps` | Listar representantes disponíveis | não |
| `GET` | `/products` | Listar produtos de interesse | não |
| `GET` | `/instructor/leads/{lead_id}` | Lead com o label de ground truth | **sim** |
| `POST` | `/instructor/leads/{lead_id}/classify` | Revelar label do LLM | **sim** |

**Total: 11 operações.**

### Como utilizar a API

**GET — listar e filtrar**

```bash
# primeira página
curl -s -H "X-Lab-Group: grupo-alfa" "$BASE/api/v1/labs/groups/01/leads?limit=2"

# leads novos de São Paulo para startups, ordenados por data
curl -s "$BASE/api/v1/labs/groups/01/leads?status=NOVO&regiao=SP&segmento=startup&sort=created_at&order=desc"

# busca livre
curl -s "$BASE/api/v1/labs/groups/01/leads?search=Granito"

#VER um lead
curl -s "$BASE/api/v1/labs/groups/01/leads/LEAD-000001"

# catálogo de apoio: quem pode receber o lead
curl -s "$BASE/api/v1/labs/groups/01/sales-reps"
curl -s "$BASE/api/v1/labs/groups/01/campaigns"
curl -s "$BASE/api/v1/labs/groups/01/products"
```

**POST — capturar, checar duplicidade, atribuir e qualificar**

```bash
# 1. verificar duplicidade antes de criar (não grava nada)
curl -s -X POST "$BASE/api/v1/labs/groups/01/leads/check-duplicates" \
  -H "Content-Type: application/json" \
  -d '{"email":"lead.0001@example.com","origem":"site"}'
# -> {"duplicate_key":"lead.0001@example.com","is_duplicate":true,"match_reason":"email", ...}

# 2. capturar o lead
curl -s -X POST "$BASE/api/v1/labs/groups/01/leads" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa" \
  -d '{
        "nome":"Ana Lima","empresa":"Empresa X",
        "email":"ana.lima@example.com","telefone":"(11) 98888-1234",
        "origem":"site","segmento":"startup","regiao":"SP",
        "produto_interesse":"PROD-01","mensagem":"Quero uma proposta."
      }'
# -> 201 {"lead_id":"LEAD-001085","status":"NOVO","duplicate_key":"ana.lima@example.com", ...}
# -> 409 {"detail":"Duplicate lead detected"} se o e-mail/telefone já existir

# 3. atribuir a um representante
curl -s -X POST "$BASE/api/v1/labs/groups/01/leads/LEAD-000001/assign" \
  -H "Content-Type: application/json" -d '{"responsavel":"SR-01"}'

# 4. qualificar
curl -s -X POST "$BASE/api/v1/labs/groups/01/leads/LEAD-000001/status" \
  -H "Content-Type: application/json" \
  -d '{"status":"CONVERTIDO","qualificado":true}'

# 5. desqualificar com motivo
curl -s -X POST "$BASE/api/v1/labs/groups/01/leads/LEAD-000001/status" \
  -H "Content-Type: application/json" \
  -d '{"status":"DESQUALIFICADO","qualificado":false,"motivo_desqualificacao":"Sem orcamento aprovado"}'
```

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `Lead` — 1.084 registros |
| Total do grupo | 1.122 registros em 4 tabelas (`Lead`, `SalesRep`, `Campaign`, `Product`) |
| `lead_id` | `LEAD-000001` |
| `campaign_id` | `CMP-001` (12 campanhas) |
| `sales_rep_id` | `SR-01` (14 representantes) |
| `product_id` | `PROD-01` (12 produtos) |
| `customer_id` de exemplo | `CUS-1001` (API original) |

---

# Grupo 02 — Ingestão de taxas do mercado primário

### Contexto de negócio

O time de tesouraria recebe planilhas XLSX de taxas do mercado primário. Cada
linha da planilha vira um registro de taxa com indexador, CNPJ do emissor,
competência e vencimento. O exercício é cadastrar o arquivo, listar as linhas
ingeridas, filtrar por indexador ou competência e baixar o XLSX determinístico.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/02
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `rate_id` | `RATE-000001` (6 dígitos) |
| path | `file_id` | `FILE-0001` (4 dígitos) |
| query | `indexador` | nome do indexador, ex. `SELIC` |
| query | `mes` | competência em `YYYY-MM`, ex. `2024-01` |
| query | `status` | status da linha, ex. `VALIDO` |
| query | `search` | case-insensitive em `emissor`, `cnpj`, `indexador`, `observacao` |
| body `POST /files` | `nome_arquivo` **obrigatório** | ex. `taxas_2026_09.xlsx` |
| body `POST /files` | `origem` **obrigatório** | ex. `tesouraria` |
| body `POST /files` | `status` | padrão `RECEIVED` |
| body `POST /files` | `created_at` | opcional |

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/rates` | Listar taxas do mercado primário | não |
| `GET` | `/rates/{rate_id}` | Obter uma taxa por id | não |
| `GET` | `/files` | Listar arquivos e status de processamento | não |
| `GET` | `/files/{file_id}` | Obter um arquivo por id | não |
| `POST` | `/files` | Registrar novo arquivo de ingestão | não |
| `GET` | `/files/{file_id}/download` | Baixar o XLSX determinístico | não |

**Total: 6 operações.**

### Como utilizar a API

**GET — listar, filtrar e baixar**

```bash
# todas as taxas, primeira página
curl -s "$BASE/api/v1/labs/groups/02/rates?limit=2"

# só SELIC
curl -s "$BASE/api/v1/labs/groups/02/rates?indexador=SELIC"

# competência específica
curl -s "$BASE/api/v1/labs/groups/02/rates?mes=2024-01"

# buscar por emissor
curl -s "$BASE/api/v1/labs/groups/02/rates?search=Kaete"

# uma taxa
curl -s "$BASE/api/v1/labs/groups/02/rates/RATE-000001"

# arquivos processados
curl -s "$BASE/api/v1/labs/groups/02/files?status=PROCESSED"

# BAIXAR O XLSX (use -OJ, não res.json())
curl -sOJ "$BASE/api/v1/labs/groups/02/files/FILE-0001/download"
# grava como mercado_primario_0001.xlsx
```

**POST — registrar um arquivo de ingestão**

```bash
curl -s -X POST "$BASE/api/v1/labs/groups/02/files" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa" \
  -d '{"nome_arquivo":"taxas_2026_09.xlsx","origem":"tesouraria"}'
# -> 201 {"file_id":"FILE-0025","nome_arquivo":"taxas_2026_09.xlsx",
#          "origem":"tesouraria","status":"RECEIVED","records_valid":0,"records_invalid":0, ...}
```

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `PrimaryMarketRate` — 1.176 registros |
| Total do grupo | 1.205 registros em 3 tabelas (`PrimaryMarketRate`, `IngestionFile`, `IndexerMapping`) |
| `rate_id` | `RATE-000001` |
| `file_id` | `FILE-0001` (24 arquivos) |
| `indexador` | `SELIC` |
| `status` da linha | `VALIDO` |
| `Content-Type` do download | `…officedocument.spreadsheetml.sheet` (XLSX) |

---

# Grupo 03 — RevOps: carga de oportunidades no Bitrix24

### Contexto de negócio

O time de Revenue Operations recebe uma lista de oportunidades em texto livre —
um e-mail colado, sem estrutura. O trabalho é parsear essa lista, quebrar em
oportunidades, validar cada linha (CNPJ, valor, produto mapeado para um
pipeline) e só então sincronizar Deals e contatos no Bitrix24. A mesma carga não
pode criar Deals duplicados, e é para isso que existe a idempotência.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/03
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `load_id` | `LOAD-0001` — **4 dígitos**, e o campo na resposta se chama `carga_id` |
| path | `opportunity_id` | `OPP-000001` |
| query `GET /loads` | `status` | status da carga |
| query `GET /loads` | `requester_email` | ex. `revops.01@example.com` |
| query `GET /opportunities` | `stage` | ex. `novo` |
| query `GET /opportunities` | `carga_id`, `produto`, `search` | `produto` ex. `CRM Enterprise` |
| query `GET /load-logs` | `carga_id`, `level` | `level` ∈ `INFO`, `WARN`, `ERROR` |
| query `GET /crm-deals` | `carga_id`, `pipeline_codigo` | ex. `PIPE-ENT` |
| query `GET /crm-contacts` | `search` | case-insensitive em `nome`, `empresa`, `email` |
| query `GET /authorized-requesters` | `active_only` | padrão `false` |
| query `GET /pipeline-maps` | `active_only` | padrão `false` |
| body `POST /loads` | `requester_email` **obrigatório** | deve ser um solicitante autorizado |
| body `POST /loads` | `lista_free_text` **obrigatório** | linhas separadas por `\n`, campos separados por `\|` |
| body `POST /opportunities/{id}/validate` | `requested_by` | padrão `manual-review` |
| header | `Idempotency-Key` | **opcional**, só este grupo dos labs |

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/loads` | Listar cargas com status e idempotência | não |
| `GET` | `/loads/{load_id}` | Obter uma carga por id | não |
| `POST` | `/loads` | Parsear lista em texto livre para Deals e contatos | não |
| `GET` | `/loads/{load_id}/crm-sync` | Deals criados para uma carga | não |
| `GET` | `/load-logs` | Logs de processamento | não |
| `GET` | `/opportunities` | Listar oportunidades derivadas | não |
| `GET` | `/opportunities/{opportunity_id}` | Obter uma oportunidade | não |
| `POST` | `/opportunities/{opportunity_id}/validate` | Reexecutar validação determinística | não |
| `GET` | `/crm-contacts` | Contatos criados no CRM | não |
| `GET` | `/crm-deals` | Deals criados de oportunidades válidas | não |
| `GET` | `/pipeline-maps` | Mapeamentos produto→pipeline | não |
| `GET` | `/authorized-requesters` | Solicitantes autorizados | não |

**Total: 12 operações.**

### Como utilizar a API

**GET — carga, logs e sincronização**

```bash
curl -s "$BASE/api/v1/labs/groups/03/loads?limit=2"
curl -s "$BASE/api/v1/labs/groups/03/loads/LOAD-0001"
curl -s "$BASE/api/v1/labs/groups/03/loads/LOAD-0001/crm-sync"

# logs de erro de uma carga
curl -s "$BASE/api/v1/labs/groups/03/load-logs?carga_id=LOAD-0001&level=ERROR"

# oportunidades de uma carga
curl -s "$BASE/api/v1/labs/groups/03/opportunities?carga_id=LOAD-0001"
curl -s "$BASE/api/v1/labs/groups/03/opportunities/OPP-000001"

# o que foi para o CRM
curl -s "$BASE/api/v1/labs/groups/03/crm-contacts?limit=2"
curl -s "$BASE/api/v1/labs/groups/03/crm-deals?pipeline_codigo=PIPE-ENT&limit=2"

# tabelas de apoio
curl -s "$BASE/api/v1/labs/groups/03/pipeline-maps?active_only=true"
curl -s "$BASE/api/v1/labs/groups/03/authorized-requesters?active_only=true"
```

**POST — enviar a lista e validar as linhas**

```bash
# 1. enviar a lista em texto livre (use Idempotency-Key para nao duplicar deals)
curl -s -X POST "$BASE/api/v1/labs/groups/03/loads" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: carga-2026-09-26-001" \
  -H "X-Lab-Group: grupo-alfa" \
  -d '{
        "requester_email":"revops.01@example.com",
        "lista_free_text":"Paranaiba Construcoes | 50.203.779/0001-10 | CRM Enterprise | 89682.57 | Karina Peixoto | karina.peixoto59@example.com | novo"
      }'
# -> 201 {"carga_id":"LOAD-0049","requester_email":"revops.01@example.com",
#          "chave_idempotencia":"...", ...}

# formato de cada linha: empresa | cnpj | produto | valor | contato | email | stage

# 2. validar uma oportunidade
curl -s -X POST "$BASE/api/v1/labs/groups/03/opportunities/OPP-000001/validate" \
  -H "Content-Type: application/json" \
  -d '{"requested_by":"manual-review"}'
# -> {"validation_id":"VAL-000001","cnpj_valido":true,"valor_valido":true,
#     "produto_mapeado":true,"motivo":"Linha pronta para sincronizacao no CRM.", ...}
```

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `Opportunity` — 1.152 registros |
| Total do grupo | 4.440 registros em 9 tabelas |
| `carga_id` (path `load_id`) | `LOAD-0001` — 48 cargas |
| `opportunity_id` | `OPP-000001` |
| `contact_id` | `CTT-000001` — 1.152 contatos |
| `deal_id` | `DEAL-000001` — 768 deals |
| `requester_id` | `REQ-001` — 12 solicitantes |
| `map_id` | `MAP-001` — 6 mapeamentos produto→pipeline |
| `pipeline_codigo` | `PIPE-ENT` (produto `CRM Enterprise`) |
| `stage` | `novo` (e `qualificado`, `proposta`, …) |
| `log_id` | `LOG-000001` — 144 logs |
| `bitrix_id` | `BTRX-392341DCF075` |

---

# Grupo 04 — Atendimento multicanal

### Contexto de negócio

O contact center recebe mensagens de vários canais (WhatsApp, e-mail, chat,
Instagram, telefone, formulário web) sobre o mesmo assunto. O exercício é
triar cada mensagem: inferir a intenção, calcular prioridade e SLA, rotear para o
departamento correto e resolver. A intenção e a confiança reais ficam
escondidas — só o endpoint de instrutor revela.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/04
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `event_id` | `EVT-000001` (6 dígitos) |
| path/query | `departamento` | id do departamento, `DEP-01` a `DEP-08` |
| query | `canal` | `whatsapp`, `email`, `chat`, `instagram`, `phone`, `web_form` |
| query | `prioridade` | `P1`, `P2`, `P3`, `P4` |
| query | `status` | `novo`, `roteado`, `resolvido` |
| query | `has_department` | `true` = só roteados, `false` = só não roteados |
| query | `search` | case-insensitive em `customer_id`, `mensagem` |
| query `GET /departments` | `active_only` | padrão `false` |
| body `POST /customer-events` | `customer_id`, `canal`, `mensagem` **obrigatórios** | — |
| body `POST /customer-events` | `impacto`, `urgencia` **obrigatórios** | **`alto`, `medio`, `baixo`** (sem acento, sem "a") |
| body `POST /customer-events` | `created_at` | opcional |
| body `POST .../route` | `departamento` **obrigatório** | `DEP-01` a `DEP-08` |
| body `POST .../resolve` | `status` | padrão `resolvido`; `resolved_at` opcional |

> **Atenção:** `impacto` e `urgencia` aceitam apenas `alto`, `medio`, `baixo`.
> Valores como `"alto"`/`"alta"` erram: a API responde
> `422 {"detail":"Impacto e urgencia devem ser alto, medio ou baixo"}`.
> A prioridade do evento é **calculada** pelo backend a partir desses dois
> campos — não envie `prioridade`.

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/customer-events` | Listar eventos sem expor labels de instrutor | não |
| `GET` | `/customer-events/{event_id}` | Obter um evento | não |
| `GET` | `/customer-events/stats` | Agregar por canal, intenção e prioridade | não |
| `POST` | `/customer-events` | Registrar intake de evento multicanal | não |
| `POST` | `/customer-events/{event_id}/route` | Atribuir evento a um departamento ativo | não |
| `POST` | `/customer-events/{event_id}/resolve` | Resolver e carimbar tempo de resolução | não |
| `GET` | `/departments` | Departamentos disponíveis para roteamento | não |
| `GET` | `/instructor/customer-events/{event_id}` | Revelar intenção e confiança ocultas | **sim** |

**Total: 8 operações.**

### Como utilizar a API

**GET — fila de atendimento**

```bash
curl -s "$BASE/api/v1/labs/groups/04/customer-events?limit=2"

# só o que ainda não foi roteado, prioridade alta
curl -s "$BASE/api/v1/labs/groups/04/customer-events?has_department=false&prioridade=P1"

# por canal
curl -s "$BASE/api/v1/labs/groups/04/customer-events?canal=whatsapp"

# um evento
curl -s "$BASE/api/v1/labs/groups/04/customer-events/EVT-000001"

# agregados
curl -s "$BASE/api/v1/labs/groups/04/customer-events/stats"

# departamentos que aceitam roteamento
curl -s "$BASE/api/v1/labs/groups/04/departments?active_only=true"
```

**POST — intake, roteamento e resolução**

```bash
# 1. registrar o evento
curl -s -X POST "$BASE/api/v1/labs/groups/04/customer-events" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa" \
  -d '{
        "customer_id":"CUS-LAB-04000",
        "canal":"whatsapp",
        "mensagem":"Quero cancelar minha assinatura.",
        "impacto":"alto",
        "urgencia":"alto"
      }'
# -> 201 {"event_id":"EVT-001145","prioridade":"P1","sla_horas":4,"status":"novo", ...}

# 2. ver os departamentos e rotear
curl -s "$BASE/api/v1/labs/groups/04/departments?active_only=true"
curl -s -X POST "$BASE/api/v1/labs/groups/04/customer-events/EVT-000001/route" \
  -H "Content-Type: application/json" -d '{"departamento":"DEP-01"}'
# -> status passa a "roteado"

# 3. resolver
curl -s -X POST "$BASE/api/v1/labs/groups/04/customer-events/EVT-000001/resolve" \
  -H "Content-Type: application/json" -d '{"status":"resolvido"}'
```

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `CustomerEvent` — 1.144 registros |
| Total do grupo | 1.152 registros em 2 tabelas |
| `event_id` | `EVT-000001` |
| `department_id` | `DEP-01` a `DEP-08` (8 departamentos) |
| Nomes dos departamentos | `Retencao`, `Pos-Venda`, `Financeiro`, `Ouvidoria`, `Relacionamento`, `Especialistas de Produto`, `Expansao`, `Fila Desativada` |
| `customer_id` de exemplo | `CUS-LAB-04000` |
| `prioridade` → SLA | `P1` → 4h, `P3` → 16h |
| `impacto` / `urgencia` | `alto`, `medio`, `baixo` |

---

# Grupo 05 — Atendimento pos-venda e-commerce

### Contexto de negócio

Depois da compra, o cliente entra em contato por vários motivos: atraso,
rastreio, defeito, troca, dúvida de uso ou segunda via de fatura. O time de
pós-venda recebe a mensagem, classifica a intenção, identifica o cliente por CPF
ou telefone para vincular o pedido, abre um ticket com SLA e responde com um
template. A intenção real fica oculta para você comparar.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/05
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `message_id` | `MSG-PV-000001` (prefixo `MSG-PV-`) |
| path | `ticket_id` | `TCK-PV-000001` |
| path | `order_id` | `PV-000001` |
| query `GET /messages` | `intencao` | see `intencao` abaixo |
| query `GET /messages` | `com_pedido` | `true` = mensagens já vinculadas a pedido |
| query `GET /messages` | `search` | case-insensitive em dados do cliente, order id e texto |
| query `GET /tickets` | `prioridade` | `alta`, `media`, `baixa` |
| query `GET /tickets` | `status` | `ABERTO`, `AGUARDANDO_IDENTIFICACAO`, `RESPONDIDO` |
| query `GET /orders` | `customer_id`, `status` | ex. `CUS-PV-00001` |
| query `GET /shipments` | `status`, `order_id`, `transportadora` | ex. `em_transito` |
| query `GET /customers` | `cpf`, `telefone`, `search` | — |
| query `GET /response-templates` | `intencao`, `ativo` | — |
| query `GET /orders/search` | `cpf` **ou** `telefone` | se o CPF faltar, usa o telefone |
| body `POST /messages` | `texto` **obrigatório** | demais campos (`customer_name`, `cpf`, `telefone`, `email`) opcionais |
| body `POST .../triage` | `intencao` **obrigatório** | `rastreio_pedido`, `reclamacao_atraso`, `defeito_produto`, `troca_produto`, `duvida_uso`, `fatura_segunda_via` |
| body `POST .../triage` | `cpf`, `telefone`, `order_id` | opcionais; use para identificar o cliente |
| body `POST .../respond` | `template_id` **obrigatório** | `TPL-0001` a `TPL-0006` (e `TPL-0091`, `TPL-0092`) |
| body `POST .../respond` | `resposta_manual` | opcional; sobrepõe o texto do template |

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/messages` | Listar mensagens com filtros e paginação | não |
| `POST` | `/messages` | Registrar mensagem recebida | não |
| `POST` | `/messages/{message_id}/triage` | Classificar, priorizar e vincular pedido | não |
| `GET` | `/instructor/messages/{message_id}` | Mensagem com label de intenção oculto | **sim** |
| `GET` | `/tickets` | Listar tickets | não |
| `GET` | `/tickets/{ticket_id}` | Obter um ticket | não |
| `POST` | `/tickets/{ticket_id}/respond` | Responder com template, idempotente | não |
| `GET` | `/orders` | Listar pedidos | não |
| `GET` | `/orders/search` | Buscar por CPF ou telefone | não |
| `GET` | `/orders/{order_id}` | Obter um pedido | não |
| `GET` | `/customers` | Listar clientes | não |
| `GET` | `/shipments` | Listar envios | não |
| `GET` | `/response-templates` | Templates de resposta | não |
| `GET` | `/stats` | Agregar por intenção, prioridade e status | não |

**Total: 14 operações.**

> `GET /stats` é uma **rota compartilhada** com o grupo 08. Respondendo ao grupo
> 05, devolve agregados de mensagens e tickets; respondendo ao grupo 08, devolve
> agregados de desbloqueio. Para qualquer outro grupo, **404**.

### Como utilizar a API

**GET — mensagens, tickets e pedidos**

```bash
curl -s "$BASE/api/v1/labs/groups/05/messages?limit=2"
curl -s "$BASE/api/v1/labs/groups/05/messages/MSG-PV-000001"

# mensagens que já têm pedido vinculado
curl -s "$BASE/api/v1/labs/groups/05/messages?com_pedido=true"

# tickets abertos de prioridade alta
curl -s "$BASE/api/v1/labs/groups/05/tickets?status=ABERTO&prioridade=alta"
curl -s "$BASE/api/v1/labs/groups/05/tickets/TCK-PV-000001"

# identificar o cliente e achar o pedido
curl -s "$BASE/api/v1/labs/groups/05/orders/search?cpf=142.570.978-84"
curl -s "$BASE/api/v1/labs/groups/05/orders?customer_id=CUS-PV-00001"
curl -s "$BASE/api/v1/labs/groups/05/orders/PV-000001"

# envios e templates
curl -s "$BASE/api/v1/labs/groups/05/shipments?order_id=PV-000001"
curl -s "$BASE/api/v1/labs/groups/05/response-templates"

# agregados (rota compartilhada com o grupo 08)
curl -s "$BASE/api/v1/labs/groups/05/stats"
```

**POST — registrar, triar e responder**

```bash
# 1. registrar a mensagem
curl -s -X POST "$BASE/api/v1/labs/groups/05/messages" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa" \
  -d '{
        "customer_name":"Rafael Azevedo",
        "cpf":"111.444.777-35",
        "telefone":"(11) 91234-5678",
        "email":"rafael.azevedo@example.com",
        "texto":"Comprei para presentear e o pedido nao chegou no prazo prometido."
      }'
# -> 201 {"message_id":"MSG-PV-001141", ...}

# 2. triar: classificar a intencao e vincular o pedido
curl -s -X POST "$BASE/api/v1/labs/groups/05/messages/MSG-PV-000001/triage" \
  -H "Content-Type: application/json" \
  -d '{"intencao":"rastreio_pedido","cpf":"111.444.777-35","order_id":"PV-000001"}'
# -> 200 {"ticket_id":"TCK-PV-000001","customer_id":"CUS-PV-00001",
#          "prioridade":"media","sla_horas":12,"resposta_template_id":"TPL-0003",
#          "status":"ABERTO", ...}

# 3. ver os templates e responder o ticket
curl -s "$BASE/api/v1/labs/groups/05/response-templates"
curl -s -X POST "$BASE/api/v1/labs/groups/05/tickets/TCK-PV-000001/respond" \
  -H "Content-Type: application/json" -d '{"template_id":"TPL-0001"}'
# -> 200 status "RESPONDIDO"
```

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `Ticket` — 1.140 registros |
| Total do grupo | 4.866 registros em 6 tabelas |
| `message_id` | `MSG-PV-000001` — 1.140 mensagens |
| `ticket_id` | `TCK-PV-000001` — 1.140 tickets |
| `order_id` | `PV-000001` — 980 pedidos |
| `customer_id` | `CUS-PV-00001` — 720 clientes |
| `shipment_id` | `SHP-PV-000001` — 878 envios |
| `template_id` | `TPL-0001` — 8 templates |
| `intencao` | `rastreio_pedido`, `reclamacao_atraso`, `defeito_produto`, `troca_produto`, `duvida_uso`, `fatura_segunda_via` |
| `prioridade` do ticket | `alta` (8h), `media` (12h), `baixa` |
| `status` do ticket | `ABERTO`, `AGUARDANDO_IDENTIFICACAO`, `RESPONDIDO` |
| `codigo_rastreio` | `BRPV0000000001` |

---

# Grupo 06 — Purchase Order

### Contexto de negócio

Uma solicitação de compra chega por e-mail, em texto livre. O trabalho é extrair
CAPEX, fornecedor, descrição e valor do corpo do e-mail, checar se o orçamento
CAPEX tem saldo, converter a solicitação em uma purchase order e conduzir o fluxo
de aprovação por etapas. Aprovar rejeita e libera o orçamentocommitted.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/06
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `request_id` | `EML-000001` (id do e-mail) |
| path | `purchase_order_number` | `PO-000001` — **o campo na resposta se chama `purchaseOrderNumber`** |
| path | `capex_number` | `CAPEX-0001` — campo `capexNumber` |
| query `GET /purchase-orders` | `status` | `RASCUNHO`, `ENVIADA_APROVACAO`, `APROVADA`, `REJEITADA`, `CONVERTIDA` |
| query | `capexNumber`, `supplierId` | `SUP-0001` a `SUP-0090` |
| query `GET /purchase-requests` | `status` | ex. `EM_ANALISE`, `APROVADO` |
| query `GET /vendors` | `categoria`, `ativo` | ex. `hardware` |
| query `GET /budgets` | `centro_custo` | ex. `CC-0200` |
| query `GET /approvals` | `purchaseOrderNumber`, `decisao` | `APROVADO`, `REJEITADO` |
| query `GET /notifications` | `canal`, `lida` | `email` |
| body `POST /email-requests` | `remetente`, `assunto`, `corpo` **obrigatórios** | ver formato abaixo |
| body `POST .../approve` e `/reject` | `stage` **obrigatório** | inteiro; começa em `1` |
| body `POST .../approve` e `/reject` | `aprovador` **obrigatório** | ex. `gerente.01` |
| body `POST .../approve` e `/reject` | `comentario` | opcional |

> **Atenção — o corpo do e-mail é parseado por regex.** O texto precisa conter
> os quatro rótulos, sem palavras extras: `CAPEX-0001`, `Fornecedor: <nome>`,
> `Itens: <descricao>` e `Valor total: R$ <valor>`. Um `de` no meio
> (`Montante estimado de R$ ...`) faz a extração falhar com
> `422 {"detail":"O corpo do e-mail nao contem dados deCompra extraiveis"}`.

> **Atenção — campos em camelCase.** As respostas deste grupo usam
> `purchaseOrderNumber`, `capexNumber` e `supplierId`, enquanto o *path param* é
> `purchase_order_number` e o *body param* de aprovação é `stage` + `aprovador`.

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/email-requests` | Listar e-mails de solicitação | não |
| `GET` | `/email-requests/{request_id}` | Obter um e-mail | não |
| `POST` | `/email-requests` | Registrar e-mail com dados extraíveis | não |
| `POST` | `/email-requests/{request_id}/extract` | Extrair solicitação por parsing determinístico | não |
| `GET` | `/purchase-requests` | Listar solicitações extraídas | não |
| `POST` | `/purchase-requests/{request_id}/check-budget` | Verificar saldo do orçamento | não |
| `POST` | `/purchase-requests/{request_id}/purchase-order` | Criar PO quando há saldo | não |
| `GET` | `/purchase-orders` | Listar purchase orders | não |
| `GET` | `/purchase-orders/{purchase_order_number}` | Obter uma PO por número | não |
| `GET` | `/purchase-orders/{purchase_order_number}/status` | Resumo do workflow da PO | não |
| `POST` | `/purchase-orders/{purchase_order_number}/submit` | Enviar rascunho para aprovação | não |
| `POST` | `/purchase-orders/{purchase_order_number}/approve` | Aprovar etapa por etapa | não |
| `POST` | `/purchase-orders/{purchase_order_number}/reject` | Rejeitar e liberar orçamento | não |
| `GET` | `/budgets` | Listar orçamentos CAPEX | não |
| `GET` | `/budgets/{capex_number}` | Obter orçamento com saldo e comprometido | não |
| `GET` | `/vendors` | Listar fornecedores | não |
| `GET` | `/approvals` | Listar decisões de aprovação | não |
| `GET` | `/notifications` | Listar notificações do workflow | não |

**Total: 18 operações.**

### Como utilizar a API

**GET — solicitações, orçamentos e o fluxo da PO**

```bash
curl -s "$BASE/api/v1/labs/groups/06/email-requests?limit=2"
curl -s "$BASE/api/v1/labs/groups/06/email-requests/EML-000001"

# solicitações extraídas
curl -s "$BASE/api/v1/labs/groups/06/purchase-requests?status=EM_ANALISE"

# POs em rascunho (as que você pode submeter)
curl -s "$BASE/api/v1/labs/groups/06/purchase-orders?status=RASCUNHO&limit=2"

# uma PO e o resumo do workflow
curl -s "$BASE/api/v1/labs/groups/06/purchase-orders/PO-000001"
curl -s "$BASE/api/v1/labs/groups/06/purchase-orders/PO-000001/status"

# orçamento com saldo e comprometido
curl -s "$BASE/api/v1/labs/groups/06/budgets/CAPEX-0001"
curl -s "$BASE/api/v1/labs/groups/06/vendors?categoria=hardware&ativo=true"

# decisões e notificações
curl -s "$BASE/api/v1/labs/groups/06/approvals?purchaseOrderNumber=PO-000001"
curl -s "$BASE/api/v1/labs/groups/06/notifications?canal=email&lida=false"
```

**POST — intake, extração, orçamento e aprovação**

```bash
# 1. registrar o e-mail (o corpo precisa ter os 4 rotulos)
curl -s -X POST "$BASE/api/v1/labs/groups/06/email-requests" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa" \
  -d '{
        "remetente":"compras@example.com",
        "assunto":"Solicitacao de compra CAPEX CAPEX-0101",
        "corpo":"Solicito abertura de compra. CAPEX CAPEX-0101. Fornecedor: Alfa Tecnologia. Itens: 5 notebooks. Valor total: R$ 12.500,00."
      }'
# -> 201 {"request_id":"EML-001121","processado":false,"purchase_request_id":null, ...}

# 2. extrair a solicitation (chamada explicita separada; o passo 1 apenas registra)
curl -s -X POST "$BASE/api/v1/labs/groups/06/email-requests/EML-001121/extract" \
  -H "Content-Type: application/json"
# -> 200 {"id":"PR-001121","email_request_id":"EML-001121","capexNumber":"CAPEX-0101",
#          "supplierId":"SUP-0060","descricao":"5 notebooks","valor_estimado":12500.0,
#          "status":"RECEBIDO", ...}

# 3. checar o orçamento (capture o id da resposta anterior)
curl -s -X POST "$BASE/api/v1/labs/groups/06/purchase-requests/PR-001121/check-budget" \
  -H "Content-Type: application/json"
# -> 200 {"purchase_request_id":"PR-001121","capexNumber":"CAPEX-0101",
#          "valor_estimado":12500.0,"saldo":238394.84,"approved":true,"missing_amount":0.0}

# 4. converter em PO, submeter e aprovar etapa a etapa
curl -s -X POST "$BASE/api/v1/labs/groups/06/purchase-requests/PR-001121/purchase-order" \
  -H "Content-Type: application/json"
# -> 201 {"purchaseOrderNumber":"PO-001121","request_id":"PR-001121", ...}

curl -s -X POST "$BASE/api/v1/labs/groups/06/purchase-orders/PO-001121/submit" \
  -H "Content-Type: application/json"
# -> status passa a "ENVIADA_APROVACAO"

curl -s -X POST "$BASE/api/v1/labs/groups/06/purchase-orders/PO-001121/approve" \
  -H "Content-Type: application/json" \
  -d '{"stage":1,"aprovador":"gerente.01","comentario":"Primeira aprovacao concluida."}'
# -> 200
```

> Use uma PO com `status=RASCUNHO` nos passos 4. Uma PO já decidida responde
> `409 {"detail":"Purchase order ja decidida"}`, e uma PO que não está em
> `RASCUNHO` responde `409 {"detail":"A purchase order so pode ser submetida a
> partir de RASCUNHO"}`.

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `PurchaseOrder` — 1.120 registros |
| Total do grupo | 5.822 registros em 7 tabelas |
| `request_id` | `EML-000001` — 1.120 e-mails |
| `id` da solicitação | `PR-000001` — 1.120 solicitações |
| `purchaseOrderNumber` | `PO-000001` — 1.120 POs |
| `capexNumber` | `CAPEX-0001` — 240 orçamentos |
| `supplierId` | `SUP-0001` — 90 fornecedores |
| `approval_id` | `APR-000001-1` — 1.235 decisões |
| `id` da notificação | `NTF-000001` — 897 notificações |
| `status` da PO | `RASCUNHO`, `ENVIADA_APROVACAO`, `APROVADA`, `REJEITADA`, `CONVERTIDA` |
| `centro_custo` | `CC-0200` |

---

# Grupo 07 — Cobrança financeira

### Contexto de negócio

O time de cobrança classifica títulos vencidos por faixa de atraso, decide a ação
adequada (e-mail, SMS, ligação, suspensão) a partir de regras de configuração,
envia a cobrança, dá baixa manual em títulos vencidos e reprocessa falhas. O
endpoint de instrutor revela a decisão esperada de cada título.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/07
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `receivable_id` | **`TIT-000001`** — o path param se chama `receivable_id`, mas o valor é o `id_titulo` |
| path | `id_titulo` (query) | `TIT-000004` |
| query `GET /receivables` | `status` | `ABERTO`, `VENCIDO`, `PAGO`, `CANCELADO` |
| query `GET /receivables` | `faixa` | `em_dia`, `1-15`, `16-30`, `31-60`, `61-90`, `90+` |
| query `GET /receivables` | `overdue_only` | padrão `false` |
| query `GET /receivables` | `customer`, `search` | `customer_id` `CLI-00001` |
| query `GET /configs` | `ativo`, `acao` | `acao` ∈ `ENVIAR_EMAIL`, `ENVIAR_SMS`, `LIGAR`, `SUSPENDER` |
| query `GET /history` | `id_titulo`, `resultado` | `resultado` ex. `SUCESSO` |
| body `POST .../bulk-send` | `faixa` **obrigatório** | uma das 6 faixas acima |
| body `POST .../bulk-send` | `limit` | padrão `100` |
| body `POST .../write-off` | `motivo` **obrigatório** | texto livre |
| body `POST /process-retry` | — | sem body |

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/receivables` | Listar recebíveis com status e aging | não |
| `GET` | `/receivables/{receivable_id}` | Obter um recebível | não |
| `GET` | `/receivables/aging` | Relatório de aging em buckets SQL | não |
| `GET` | `/receivables/{receivable_id}/collection-decision` | Qual ação de cobrança se aplica | não |
| `POST` | `/receivables/{receivable_id}/send-collection` | Enviar ação, idempotente no mesmo dia | não |
| `POST` | `/receivables/{receivable_id}/write-off` | Baixar recebível para CANCELADO | não |
| `POST` | `/receivables/bulk-send` | Lote por bucket com falha parcial | não |
| `GET` | `/history` | Listar eventos do histórico de cobrança | não |
| `GET` | `/configs` | Listar regras de configuração | não |
| `POST` | `/process-retry` | Retentar falhas de forma idempotente | não |
| `GET` | `/instructor/receivables/{receivable_id}` | Recebível com decisão de envio oculta | **sim** |

**Total: 11 operações.**

> `GET /history` é uma **rota compartilhada** com o grupo 08. Respondendo ao
> grupo 07, devolve o histórico de cobrança (`HIS-*`); respondendo ao grupo 08,
> devolve o histórico de desbloqueio (`UHI-*`). Para qualquer outro grupo,
> **404**.

### Como utilizar a API

**GET — aging, decisão e histórico**

```bash
curl -s "$BASE/api/v1/labs/groups/07/receivables?limit=2"

# só vencidos, na faixa 16-30
curl -s "$BASE/api/v1/labs/groups/07/receivables?overdue_only=true&faixa=16-30"

# relatório de aging por bucket
curl -s "$BASE/api/v1/labs/groups/07/receivables/aging"
# -> {"faixa":"1-15","quantidade":267,"valor_total":3955817.09}

# um título e a ação que se aplica a ele
curl -s "$BASE/api/v1/labs/groups/07/receivables/TIT-000001"
curl -s "$BASE/api/v1/labs/groups/07/receivables/TIT-000001/collection-decision"

# regras de configuração e histórico
curl -s "$BASE/api/v1/labs/groups/07/configs?ativo=true"
curl -s "$BASE/api/v1/labs/groups/07/history?id_titulo=TIT-000004"
```

**POST — cobrança unitária, em lote, baixa e retry**

```bash
# 1. enviar a ação de cobrança do título
curl -s -X POST "$BASE/api/v1/labs/groups/07/receivables/TIT-000001/send-collection" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa"
# -> 200 {"id":"HIS-001157","acao":"IGNORADO","resultado":"...", ...}
#    TIT-000001 ja esta PAGO, por isso o resultado e IGNORADO.
#    Um titulo vencido (ex. TIT-000004) retorna ENVIAR_EMAIL com SUCESSO.

# 2. ou em lote, por faixa de atraso
curl -s -X POST "$BASE/api/v1/labs/groups/07/receivables/bulk-send" \
  -H "Content-Type: application/json" \
  -d '{"faixa":"1-15","limit":5}'
# -> 200 {"processed":5,"success":4,"failed":0,"ignored":1,"outcomes":[...]}
#    Titulos ja pagos ou fora da regra retornam como IGNORADO.

# 3. dar baixa manual
curl -s -X POST "$BASE/api/v1/labs/groups/07/receivables/TIT-000001/write-off" \
  -H "Content-Type: application/json" \
  -d '{"motivo":"Cliente nao localizado apos 3 tentativas."}'
# -> 200 status passa a "CANCELADO"

# 4. reprocessar as falhas
curl -s -X POST "$BASE/api/v1/labs/groups/07/process-retry" \
  -H "Content-Type: application/json"
# -> 200 {"processed":13,"items":[...]}
```

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `Receivable` — 1.150 registros |
| Total do grupo | 1.450 registros em 3 tabelas |
| `id_titulo` (path `receivable_id`) | `TIT-000001` |
| `customer_id` | `CLI-00001` |
| `customer_document` | `70.970.559/0001-21` (CNPJ) |
| `config_id` | `CFG-0001` a `CFG-0005` (5 regras) |
| `id` do histórico | `HIS-000004` — 295 eventos |
| `status` do título | `ABERTO`, `VENCIDO`, `PAGO`, `CANCELADO` |
| `faixa` | `em_dia`, `1-15`, `16-30`, `31-60`, `61-90`, `90+` |
| `acao` da regra | `ENVIAR_EMAIL`, `ENVIAR_SMS`, `LIGAR`, `SUSPENDER` |
| Configuração por faixa | `1-15`→e-mail, `16-30`→SMS, `31-60`→ligação, `61-90`→e-mail (escalada formal), `91+`→suspensão |

---

# Grupo 08 — Desbloqueio em confiança

### Contexto de negócio

Um cliente com serviço suspenso pede desbloqueio. O time de análise registra a
solicitação, roda a consulta de crédito, aceita uma promessa de pagamento e
aplica a regra de decisão — liberar, liberar parcialmente ou negar. Se liberar,
o provisionamento é um mock. O endpoint de instrutor revela a decisão esperada.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/08
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `request_id` | `UR-000001` |
| path | `customer_id` | `UC-000001` |
| query `GET /unlock-requests` | `status` | `RECEBIDO`, `EM_ANALISE`, `AGUARDANDO_PROMESSA`, `APROVADO`, `REJEITADO` |
| query `GET /unlock-requests` | `customer_id`, `search` | — |
| query `GET /contracts` | `contract_status` | `ATIVO` |
| query `GET /invoices` | `customer_id`, `status` | `ABERTA`, `PAGA`, `VENCIDA` |
| query `GET /credit-checks` | `customer_id`, `resultado` | `APROVADO`, `REJEITADO`, `ANALISE_MANUAL` |
| query `GET /unlock-history` | `request_id`, `acao` | `acao` ex. `CRIAR` |
| body `POST /unlock-requests` | `customer_id` **obrigatório** | `UC-000001` |
| body `POST /unlock-requests` | `motivo` **obrigatório** | texto livre |
| body `POST .../promise` | `promessa_pagamento_data` **obrigatório** | data `YYYY-MM-DD`, ex. `2026-09-30` |
| body `POST .../decide` e `/provision` | `executed_by` | **opcional**, padrão `analista.lab` |

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/unlock-requests` | Listar solicitações de desbloqueio | não |
| `GET` | `/unlock-requests/{request_id}` | Obter uma solicitação | não |
| `POST` | `/unlock-requests` | Registrar solicitação de desbloqueio | não |
| `POST` | `/unlock-requests/{request_id}/credit-check` | Consulta de crédito simulada | não |
| `POST` | `/unlock-requests/{request_id}/promise` | Registrar promessa de pagamento | não |
| `POST` | `/unlock-requests/{request_id}/decide` | Aplicar regra determinística de decisão | não |
| `POST` | `/unlock-requests/{request_id}/provision` | Provisionar quando liberado | não |
| `GET` | `/unlock-stats` | Agregados de desbloqueio | não |
| `GET` | `/instructor/unlock-requests/{request_id}` | Solicitação com decisão esperada | **sim** |
| `GET` | `/contracts` | Listar contratos | não |
| `GET` | `/contracts/{customer_id}/summary` | Contrato, faturas e última consulta de crédito | não |
| `GET` | `/credit-checks` | Listar consultas de crédito | não |
| `GET` | `/invoices` | Listar faturas do contrato | não |
| `GET` | `/unlock-history` | Listar histórico do workflow | não |

**Total: 14 operações.**

> Este grupo tem rota própria e rota compartilhada para os dois recursos, e
> ambas respondem em produção com JSON idêntico (verificado em produção:
> `unlock-stats` ≡ `stats` e `unlock-history` ≡ `history`). A rota
> compartilhada `GET /stats` e a `GET /history` respondem pelo `group_id` da
> URL e devolvem `404` para qualquer outro grupo. Prefira os paths próprios em
> código novo.

### Como utilizar a API

**GET — solicitações, contrato e agregados**

```bash
curl -s "$BASE/api/v1/labs/groups/08/unlock-requests?limit=2"
curl -s "$BASE/api/v1/labs/groups/08/unlock-requests/UR-000001"

# por status
curl -s "$BASE/api/v1/labs/groups/08/unlock-requests?status=AGUARDANDO_PROMESSA"

# contrato, faturas e crédito do cliente
curl -s "$BASE/api/v1/labs/groups/08/contracts?contract_status=ATIVO"
curl -s "$BASE/api/v1/labs/groups/08/contracts/UC-000001/summary"
curl -s "$BASE/api/v1/labs/groups/08/invoices?customer_id=UC-000001"
curl -s "$BASE/api/v1/labs/groups/08/credit-checks?customer_id=UC-000001"

# agregados: use a rota compartilhada que já está em produção
curl -s "$BASE/api/v1/labs/groups/08/stats"
# -> {"requests_by_status":{"AGUARDANDO_PROMESSA":185,"APROVADO":59,"EM_ANALISE":148,
#            "RECEBIDO":592,"REJEITADO":126},
#      "decisions_by_type":{"LIBERADO":59,"NEGADO":102,"PARCIAL":24}}
```

**POST — fluxo completo de desbloqueio**

```bash
# 1. registrar a solicitação
curl -s -X POST "$BASE/api/v1/labs/groups/08/unlock-requests" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa" \
  -d '{"customer_id":"UC-000001",
       "motivo":"Consumidor deseja liberar o acesso para manter a operacao enquanto regulariza a fatura."}'
# -> 201 {"request_id":"UR-001111","protocol":"PRT-00001111","status":"RECEBIDO", ...}

# 2. consulta de crédito simulada
curl -s -X POST "$BASE/api/v1/labs/groups/08/unlock-requests/UR-000001/credit-check" \
  -H "Content-Type: application/json"
# -> 200 {"check_id":"CHK-000001","score":357,"limite_credito":720.0,
#          "usado":720.0,"disponivel":0.0,"resultado":"REJEITADO", ...}

# 3. registrar a promessa de pagamento
curl -s -X POST "$BASE/api/v1/labs/groups/08/unlock-requests/UR-000001/promise" \
  -H "Content-Type: application/json" \
  -d '{"promessa_pagamento_data":"2026-09-30"}'
# -> 200 status passa a "AGUARDANDO_PROMESSA"

# 4. aplicar a regra de decisão (executed_by e opcional)
curl -s -X POST "$BASE/api/v1/labs/groups/08/unlock-requests/UR-000001/decide" \
  -H "Content-Type: application/json" \
  -d '{"executed_by":"analista.lab"}'
# -> 200 {"decision_id":"DEC-000001","decision":"NEGADO",
#          "justification":"Risco de credito ou inadimplencia acima do tolerado para desbloqueio.", ...}

# 5. se a decisão foi LIBERADO, provisionar
curl -s -X POST "$BASE/api/v1/labs/groups/08/unlock-requests/UR-000001/provision" \
  -H "Content-Type: application/json" \
  -d '{"executed_by":"analista.lab"}'
```

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `UnlockRequest` — 1.110 registros |
| Total do grupo | 6.391 registros em 6 tabelas |
| `request_id` | `UR-000001` |
| `protocol` | `PRT-00000001` |
| `customer_id` | `UC-000001` — 760 contratos |
| `invoice_id` | `INV-000001-01` — 2.383 faturas |
| `check_id` | `CHK-000001` — 380 consultas de crédito |
| `history_id` | `UHI-000001-1` — 1.573 eventos |
| `decision_id` | `DEC-000001` |
| `status` da solicitação | `RECEBIDO`, `EM_ANALISE`, `AGUARDANDO_PROMESSA`, `APROVADO`, `REJEITADO` |
| `decision` | `LIBERADO`, `PARCIAL`, `NEGADO` |
| `resultado` do crédito | `APROVADO`, `REJEITADO`, `ANALISE_MANUAL` |
| `contract_status` | `ATIVO` |

---

# Grupo 09 — Onboarding de RH

### Contexto de negócio

Um candidato foi aprovado e precisa ser onboardado: abrir o registro, concede
acessos a sistemas por nível de permissão, solicitar equipamentos, registrar as
verificações de segurança e acompanhar as tarefas até a conclusão. O exercício
inclui lidar com exceções de admissão. O ground truth do candidato está no
endpoint de instrutor.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/09
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `candidate_id` | **`CAND-00001`** — o path param se chama `candidate_id`, mas o campo na resposta é `id_candidato` |
| path | `equipment_id` | `EQP-00001-1` |
| query `GET /candidates` | `status` | `APROVADO`, `EM_ANALISE`, `EM_ONBOARDING`, `CONCLUIDO`, `REJEITADO` |
| query `GET /candidates` | `departamento` | `Tecnologia`, `Financeiro`, `RH`, `Jurídico`, `Marketing`, `Operacoes` |
| query `GET /candidates` | `admissao_excecao`, `search` | — |
| query `GET /access-matrix` | `candidate_id`, `nivel_acesso` | `LEITURA`, `ESCRITA`, `ADMIN` |
| query `GET /equipment` | `candidate_id`, `status` | `SOLICITADO`, `EMPRESTADO` |
| query `GET /security-approvals` | `candidate_id`, `status` | `PENDENTE`, `APROVADO`, `REPROVADO`, `EXCEPCAO_APROVADA` |
| query `GET /tasks` | `candidate_id`, `concluida` | — |
| body `POST /candidates` | `nome`, `email`, `cpf`, `cargo`, `departamento`, `data_admissao`, `decisao_admissao_esperada` **obrigatórios** | ver abaixo |
| body `POST /candidates` | `admissao_excecao` | padrão `false`; `admissao_motivo` opcional |
| body `POST .../access-matrix` | `sistema`, `perfil`, `nivel_acesso` **obrigatórios** | `sistema` ∈ `hris`, `erp-financeiro`, `crm`, `bi`, `service-desk`; `perfil` ∈ `basico`, `analista`, `gestor` |
| body `POST .../access-matrix` | `aprovado` | padrão `true`; `aprovador` opcional |
| body `POST .../equipment` | `tipo`, `modelo`, `serial`, `solicitacao_motivo` **obrigatórios** | `tipo` ∈ `NOTEBOOK`, `MONITOR`, `CRACHA` |
| body `POST .../security-approvals` | `tipo_verificacao`, `status` **obrigatórios** | `tipo_verificacao` ∈ `BACKGROUND_CHECK`, `ANTECEDENTES`, `RG_CPF`, `ACESSO_PRECIFICADO` |
| body `POST .../security-approvals` | `verificado_por`, `parecer` | opcionais |
| body `POST /equipment/{id}/issue` | — | sem body |

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/candidates` | Listar candidatos | não |
| `GET` | `/candidates/{candidate_id}` | Obter um candidato | não |
| `POST` | `/candidates` | Criar registro de intake | não |
| `GET` | `/candidates/{candidate_id}/onboarding-status` | Status consolidado do onboarding | não |
| `GET` | `/instructor/candidates/{candidate_id}` | Ground truth do candidato | **sim** |
| `POST` | `/candidates/{candidate_id}/access-matrix` | Conceder acesso | não |
| `POST` | `/candidates/{candidate_id}/equipment` | Solicitar equipamento | não |
| `POST` | `/candidates/{candidate_id}/security-approvals` | Registrar verificação de segurança | não |
| `GET` | `/access-matrix` | Listar linhas de matriz de acesso | não |
| `GET` | `/equipment` | Listar equipamentos solicitados | não |
| `POST` | `/equipment/{equipment_id}/issue` | Emitir equipamento | não |
| `GET` | `/onboardings` | Listar registros de onboarding | não |
| `GET` | `/tasks` | Listar tarefas | não |
| `GET` | `/security-approvals` | Listar aprovações de segurança | não |
| `GET` | `/onboarding-stats` | Agregados de onboarding | não |

**Total: 15 operações.**

### Como utilizar a API

**GET — candidatos e progresso**

```bash
curl -s "$BASE/api/v1/labs/groups/09/candidates?limit=2"
curl -s "$BASE/api/v1/labs/groups/09/candidates/CAND-00001"

# candidatos aprovados com exceção de admissão
curl -s "$BASE/api/v1/labs/groups/09/candidates?status=APROVADO&admissao_excecao=true"

# progresso consolidado
curl -s "$BASE/api/v1/labs/groups/09/candidates/CAND-00001/onboarding-status"

# acessos, equipamentos, verificações e tarefas do candidato
curl -s "$BASE/api/v1/labs/groups/09/access-matrix?candidate_id=CAND-00001"
curl -s "$BASE/api/v1/labs/groups/09/equipment?candidate_id=CAND-00001&status=SOLICITADO"
curl -s "$BASE/api/v1/labs/groups/09/security-approvals?candidate_id=CAND-00001"
curl -s "$BASE/api/v1/labs/groups/09/tasks?candidate_id=CAND-00001&concluida=false"

# agregados
curl -s "$BASE/api/v1/labs/groups/09/onboarding-stats"
```

**POST — intake e onboarding**

```bash
# 1. criar o intake do candidato
curl -s -X POST "$BASE/api/v1/labs/groups/09/candidates" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa" \
  -d '{
        "nome":"Joana Souza",
        "email":"joana.souza@example.com",
        "cpf":"390.533.447-05",
        "cargo":"Analista de Dados",
        "departamento":"Tecnologia",
        "data_admissao":"2026-10-01",
        "decisao_admissao_esperada":"APROVADO"
      }'
# -> 201 {"id_candidato":"CAND-001033","status":"EM_ANALISE", ...}

# 2. conceder acesso (capture o id_candidato da resposta anterior)
curl -s -X POST "$BASE/api/v1/labs/groups/09/candidates/CAND-00001/access-matrix" \
  -H "Content-Type: application/json" \
  -d '{"sistema":"hris","perfil":"basico","nivel_acesso":"LEITURA"}'
# -> 201 {"id":"ACC-CAND-00001-2","aprovado":true, ...}

# 3. solicitar equipamento
curl -s -X POST "$BASE/api/v1/labs/groups/09/candidates/CAND-00001/equipment" \
  -H "Content-Type: application/json" \
  -d '{"tipo":"NOTEBOOK","modelo":"QuantumBook Pro 14","serial":"G09-00001-9","solicitacao_motivo":"Kit padrao de admissao"}'
# -> 201 {"id":"EQP-CAND-00001-3","status":"SOLICITADO", ...}

# 4. registrar a verificacao de seguranca
curl -s -X POST "$BASE/api/v1/labs/groups/09/candidates/CAND-00001/security-approvals" \
  -H "Content-Type: application/json" \
  -d '{"tipo_verificacao":"BACKGROUND_CHECK","status":"APROVADO","verificado_por":"seg.1"}'
# -> 200 {"id":"SAP-CAND-00001-5", ...}

# 5. emitir o equipamento (o EquipmentIssueBookResponse nao retorna o
#    equipamento; capture o id da resposta do passo 3)
curl -s -X POST "$BASE/api/v1/labs/groups/09/equipment/EQP-00001-1/issue" \
  -H "Content-Type: application/json"
# -> 200 status passa a "EMPRESTADO"
```

> Os passos 2 a 5 usam o candidato semeado `CAND-00001` para que as respostas
> observadas sejam as do seed. Em um script real, troque por `CAND-001033`
> (o `id_candidato` do passo 1) e capture o `id` de cada resposta — o passo 3
> devolve `EQP-...` e o passo 4 devolve `SAP-...`. O passo 5 é a única
> transição de estado sobre equipamento e precisa de um `SOLICITADO`
> diferente do que foi emitido.

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `Candidate` — 1.032 registros |
| Total do grupo | 14.792 registros em 6 tabelas |
| `id_candidato` (path `candidate_id`) | `CAND-00001` |
| `id` da matriz de acesso | `ACC-00001-1` — 1.032 linhas |
| `id` do equipamento | `EQP-00001-1` — 2.408 equipamentos |
| `id` da verificação | `SAP-00001-1` — 4.128 verificações |
| `id_onboarding` | `ONB-00001` |
| `id` da tarefa | `TSK-00001-1` — 5.160 tarefas |
| `status` do candidato | `APROVADO`, `EM_ANALISE`, `EM_ONBOARDING`, `CONCLUIDO`, `REJEITADO` |
| `nivel_acesso` | `LEITURA`, `ESCRITA`, `ADMIN` |
| `sistema` | `hris`, `erp-financeiro`, `crm`, `bi`, `service-desk` |
| `perfil` | `basico`, `analista`, `gestor` |
| `departamento` | `Tecnologia`, `Financeiro`, `RH`, `Jurídico`, `Marketing`, `Operacoes` |
| `cargo` | `Analista de Dados`, `Analista Financeiro`, `Analista de Marketing`, `Coordenador de Operacoes`, `Business Partner RH`, `Especialista em Seguranca` |

---

# Grupo 10 — Clínica: confirmação de consultas

### Contexto de negócio

Uma clínica atende por WhatsApp. O paciente manda mensagem para confirmar, cancelar
ou remarcar a consulta, e às vezes a mensagem é ambígua e exige revisão humana.
O fluxo é classificar a intenção, aplicá-la à consulta vinculada, os horários
livres da lista de espera e registrar tudo no log do workflow. A classificação
real fica escondida para você comparar.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/10
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `message_id` | `MSG-000001` |
| path | `appointment_id` | `APT-000001` |
| path | `waitlist_id` | `WTL-000003` |
| path | `slot_id` | `SLT-00001` |
| path | `professional_id` | `PRO-001` — 16 profissionais |
| query `GET /patient-messages` | `intent` | `CONFIRMAR`, `CANCELAR`, `REMARCAR`, `DUVIDA`, `RECUSA`, `RUIDO`, `SAUDACAO` |
| query `GET /patient-messages` | `human_review` | `true`/`false` |
| query `GET /patient-messages` | `search` | — |
| query `GET /appointments` | `status` | `AGENDADA`, `CONFIRMADA`, `REMARCADA`, `CANCELADA_POR_PACIENTE` |
| query `GET /appointments` | `professional`, `start_at`, `end_at`, `search` | — |
| query `GET /slots` | `professional`, `disponivel`, `date` | `disponivel=true` retorna os livres |
| query `GET /waitlist` | `patient_id`, `status` | `AGUARDANDO`, `OFERECIDO` |
| query `GET /workflow-logs` | `appointment_id`, `message_id` | — |
| body `POST /patient-messages` | `wa_id`, `telefone`, `mensagem` **obrigatórios** | `wa_id` ex. `wa-5511000000001` — **único**, repetir → 409 |
| body `POST .../classify` | `intent`, `confianca`, `origem`, `reviewed_by` | todos opcionais; `origem` padrão `REGRA`; `confianca` é `0.0`–`1.0` |
| body `POST /waitlist` | `patient_id`, `especialidade`, `preferencia_data` **obrigatórios** | `especialidade` ∈ `Cardiologia`, `Dermatologia`, `Neurologia`, `Ortopedia`, `Pediatria` |
| body `POST .../confirm`, `/cancel`, `/reschedule`, `/offer` | — | sem body |

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/patient-messages` | Listar mensagens do paciente | não |
| `GET` | `/patient-messages/{message_id}` | Obter uma mensagem | não |
| `POST` | `/patient-messages` | Ingerir mensagem de WhatsApp | não |
| `POST` | `/patient-messages/{message_id}/classify` | Classificar ou revisar mensagem | não |
| `POST` | `/patient-messages/{message_id}/apply` | Aplicar intenção à consulta vinculada | não |
| `GET` | `/patient-messages/{message_id}/history` | Histórico do workflow da mensagem | não |
| `GET` | `/instructor/patient-messages/{message_id}` | Campos de classificação ocultos | **sim** |
| `GET` | `/appointments` | Listar consultas | não |
| `GET` | `/appointments/{appointment_id}` | Obter uma consulta | não |
| `POST` | `/appointments/{appointment_id}/confirm` | Confirmar consulta | não |
| `POST` | `/appointments/{appointment_id}/cancel` | Cancelar consulta | não |
| `POST` | `/appointments/{appointment_id}/reschedule` | Remendar consulta | não |
| `GET` | `/slots` | Listar horários disponíveis | não |
| `GET` | `/waitlist` | Listar lista de espera | não |
| `POST` | `/waitlist` | Entrar na lista de espera | não |
| `POST` | `/waitlist/{waitlist_id}/offer` | Oferecer horário livre | não |
| `GET` | `/professionals` | Listar profissionais de saúde | não |
| `GET` | `/workflow-logs` | Listar logs do workflow | não |
| `GET` | `/clinic-stats` | Agregados da clínica | não |

**Total: 19 operações.**

### Como utilizar a API

**GET — agenda, horários e lista de espera**

```bash
curl -s "$BASE/api/v1/labs/groups/10/patient-messages?limit=2"
curl -s "$BASE/api/v1/labs/groups/10/patient-messages/MSG-000001"
curl -s "$BASE/api/v1/labs/groups/10/patient-messages/MSG-000001/history"

# mensagens que precisam de revisao humana
curl -s "$BASE/api/v1/labs/groups/10/patient-messages?human_review=true"

# agenda
curl -s "$BASE/api/v1/labs/groups/10/appointments?status=AGENDADA&limit=2"
curl -s "$BASE/api/v1/labs/groups/10/appointments/APT-000001"

# horarios livres
curl -s "$BASE/api/v1/labs/groups/10/slots?disponivel=true&limit=2"

# profissionais e lista de espera
curl -s "$BASE/api/v1/labs/groups/10/professionals"
curl -s "$BASE/api/v1/labs/groups/10/waitlist?status=AGUARDANDO"
curl -s "$BASE/api/v1/labs/groups/10/workflow-logs?appointment_id=APT-000001"
curl -s "$BASE/api/v1/labs/groups/10/clinic-stats"
```

**POST — intake, classificação e agenda**

```bash
# 1. ingerir a mensagem do WhatsApp (wa_id precisa ser inedito)
curl -s -X POST "$BASE/api/v1/labs/groups/10/patient-messages" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa" \
  -d '{"wa_id":"wa-5511999999999","telefone":"7199999999","mensagem":"Confirmo minha consulta."}'
# -> 201 {"message_id":"MSG-001049","human_review":false, ...}
# -> 409 {"detail":"wa_id already exists"} se o wa_id ja existir

# 2. classificar (revisao humana quando a confianca e baixa)
curl -s -X POST "$BASE/api/v1/labs/groups/10/patient-messages/MSG-000001/classify" \
  -H "Content-Type: application/json" \
  -d '{"intent":"CONFIRMAR","confianca":0.95,"origem":"REGRA"}'
# -> 200 {"id":"LBL-001049","message_id":"MSG-000001","intent":"CONFIRMAR","confianca":0.95, ...}

# 3. aplicar a intencao a consulta vinculada
curl -s -X POST "$BASE/api/v1/labs/groups/10/patient-messages/MSG-000001/apply" \
  -H "Content-Type: application/json"

# 4. ou agir direto na consulta (cada acao consome o agendamento, use um por acao)
curl -s -X POST "$BASE/api/v1/labs/groups/10/appointments/APT-000004/confirm" \
  -H "Content-Type: application/json"
# -> 200 CONFIRMADA

curl -s -X POST "$BASE/api/v1/labs/groups/10/appointments/APT-000006/cancel" \
  -H "Content-Type: application/json"
# -> 200 CANCELADA_POR_PACIENTE

curl -s -X POST "$BASE/api/v1/labs/groups/10/appointments/APT-000007/reschedule" \
  -H "Content-Type: application/json"
# -> 200 REMARCADA

# 5. lista de espera
curl -s -X POST "$BASE/api/v1/labs/groups/10/waitlist" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"wa-5511000000003","especialidade":"Cardiologia","preferencia_data":"2026-09-20T14:00:00"}'
# -> 201 {"id":"WTL-001047","status":"AGUARDANDO", ...}
curl -s -X POST "$BASE/api/v1/labs/groups/10/waitlist/WTL-000003/offer" \
  -H "Content-Type: application/json"
# -> 200 {"status":"OFERECIDO","offered_slot_id":"SLT-00200", ...}
```

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `Appointment` — 1.048 registros |
| Total do grupo | 4.598 registros em 7 tabelas |
| `message_id` | `MSG-000001` — 1.048 mensagens |
| `appointment_id` | `APT-000001` — 1.048 consultas |
| `professional_id` | `PRO-001` — 16 profissionais |
| `slot_id` | `SLT-00001` — 240 slots |
| `waitlist_id` | `WTL-000003` — 150 entradas |
| `id` do log | `WFL-000001` — 1.048 logs |
| `wa_id` | `wa-5511000000001` — **único por paciente** |
| `intent` | `CONFIRMAR`, `CANCELAR`, `REMARCAR`, `DUVIDA`, `RECUSA`, `RUIDO`, `SAUDACAO` |
| `status` da consulta | `AGENDADA`, `CONFIRMADA`, `REMARCADA`, `CANCELADA_POR_PACIENTE` |
| `especialidade` | `Cardiologia`, `Dermatologia`, `Neurologia`, `Ortopedia`, `Pediatria` |

---

# Grupo 11 — Evidências de restore

### Contexto de negócio

Depois de um restore de sistema, alguém precisa anexar a evidência do que foi
testado: configuração, data/hora, resultado, versão antes e depois, duração e
responsável. O exercício é revisar essa evidência, detectar divergências e
campos faltantes, registrar o parecer no registro de evidências e abrir um plano
de ação quando o restore falhar.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/11
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `email_id` | `EML-000001` — 1.024 e-mails |
| path | `evidence_id` | `EVD-000001` — 1.024 evidências |
| path | `action_plan_id` | `ACT-000004` — 409 planos |
| path/body | `IC` | `IC-000001` — **único**, ver aviso abaixo |
| query `GET /emails` | `severidade` | `ALTA`, `MEDIA`, `BAIXA` |
| query `GET /emails` | `search` | — |
| query `GET /evidence` | `resultado` | `SUCESSO`, `PARCIAL`, `FALHA` |
| query `GET /evidence` | `sistema` | `erp`, `crm`, `billing`, `dw` |
| query `GET /registry` | `status` | `EM_ANALISE`, `APROVADO`, `REPROVADO` |
| query `GET /action-plans` | `evidence_id`, `status` | `PENDENTE`, `CONCLUIDA` |
| body `POST /emails` | `remetente`, `assunto`, `corpo`, `ticket_mudanca`, `severidade` **obrigatórios** | `ticket_mudanca` ex. `CHG-2001` |
| body `POST /emails/{id}/evidence` | `IC`, `data_hora_teste`, `resultado`, `sistema`, `versao_antes`, `duracao_seg`, `responsavel` **obrigatórios** | — |
| body `POST .../evidence` | `versao_depois`, `observacoes`, `has_prints` | opcionais; `has_prints` padrão `false` |
| body `POST .../review` | `status`, `analisado_por` **obrigatórios** | `parecer` opcional |
| body `POST .../action-plans` | `acao`, `prazo`, `responsavel` **obrigatórios** | `prazo` é data `YYYY-MM-DD` |
| body `POST .../complete` | `conclusao` **obrigatório** | texto livre |

> ⚠️ **O campo `IC` tem restrição de unicidade.** Enviar um `IC` que já existe
> (por exemplo `IC-000002`, que já está no seed) provoca **HTTP 500** em vez de
> um `409`. Use sempre um `IC` inédito, como `IC-999999`. Veja o
> [Apêndice F](#apêndice-f--pendências-conhecidas).

> A análise de divergência é determinística: `versao_depois` ausente vira
> `divergent_fields: ["versao_depois"]`. Um campo obrigatório ausente (como
> `observacoes`) vira `missing_fields: ["observacoes"]`. Quando qualquer uma
> das listas não está vazia, a decisão determinística é `REPROVADO`.

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/emails` | Listar e-mails recebidos | não |
| `GET` | `/emails/{email_id}` | Obter um e-mail | não |
| `POST` | `/emails` | Intake de um e-mail | não |
| `POST` | `/emails/{email_id}/evidence` | Anexar evidência a um e-mail | não |
| `GET` | `/evidence` | Listar evidências de restore | não |
| `GET` | `/evidence/{evidence_id}` | Obter uma evidência | não |
| `GET` | `/evidence/{evidence_id}/analysis` | Análise de divergência determinística | não |
| `GET` | `/evidence/{evidence_id}/pdf` | Baixar o PDF determinístico | não |
| `POST` | `/evidence/{evidence_id}/review` | Registrar revisão no registro | não |
| `GET` | `/instructor/evidence/{evidence_id}` | Ground truth da evidência | **sim** |
| `GET` | `/action-plans` | Listar planos de ação | não |
| `POST` | `/evidence/{evidence_id}/action-plans` | Criar plano de ação | não |
| `POST` | `/action-plans/{action_plan_id}/complete` | Concluir plano de ação | não |
| `GET` | `/registry` | Listar linhas do registro de evidências | não |
| `GET` | `/evidence-stats` | Agregados de evidências | não |

**Total: 15 operações.**

### Como utilizar a API

**GET — e-mails, evidências e análise**

```bash
curl -s "$BASE/api/v1/labs/groups/11/emails?severidade=ALTA&limit=2"
curl -s "$BASE/api/v1/labs/groups/11/emails/EML-000001"

curl -s "$BASE/api/v1/labs/groups/11/evidence?resultado=FALHA&limit=2"
curl -s "$BASE/api/v1/labs/groups/11/evidence/EVD-000001"

# analise de divergencia
curl -s "$BASE/api/v1/labs/groups/11/evidence/EVD-000001/analysis"
# -> {"evidence_id":"EVD-000001","IC":"IC-000001","has_prints":true,
#     "divergent_fields":[],"missing_fields":[]}

# baixar o PDF (use -OJ, nao res.json())
curl -sOJ "$BASE/api/v1/labs/groups/11/evidence/EVD-000001/pdf"

# registro e planos de acao
curl -s "$BASE/api/v1/labs/groups/11/registry?status=EM_ANALISE"
curl -s "$BASE/api/v1/labs/groups/11/action-plans?evidence_id=EVD-000004&status=PENDENTE"
curl -s "$BASE/api/v1/labs/groups/11/evidence-stats"
```

**POST — intake, evidência, parecer e plano de ação**

```bash
# 1. registrar o e-mail de solicitacao
curl -s -X POST "$BASE/api/v1/labs/groups/11/emails" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa" \
  -d '{
        "remetente":"daniela.moura78@example.org",
        "assunto":"Solicitacao de evidencia de restore CHG-2001",
        "corpo":"Favor anexar a evidencia do restore executado apos a janela de manutencao.",
        "ticket_mudanca":"CHG-2001",
        "severidade":"ALTA"
      }'
# -> 201 {"email_id":"EML-001025", ...}

# 2. anexar a evidencia (capture o id do passo anterior e use um IC inedito)
curl -s -X POST "$BASE/api/v1/labs/groups/11/emails/EML-001025/evidence" \
  -H "Content-Type: application/json" \
  -d '{
        "IC":"IC-999999",
        "data_hora_teste":"2026-09-13T09:30:00",
        "resultado":"SUCESSO",
        "sistema":"erp",
        "versao_antes":"1.8.2",
        "versao_depois":"1.8.3",
        "duracao_seg":640,
        "responsavel":"analista.restore",
        "observacoes":"Restore executado com sucesso.",
        "has_prints":true
      }'
# -> 201 {"evidence_id":"EVD-001025","IC":"IC-999999", ...}

# 3. registrar o parecer no registro de evidencias (capture o evidence_id)
curl -s -X POST "$BASE/api/v1/labs/groups/11/evidence/EVD-001025/review" \
  -H "Content-Type: application/json" \
  -d '{"status":"APROVADO","analisado_por":"reviewer.1","parecer":"Evidencia coerente."}'
# -> 200 {"id":"REG-000001","status":"APROVADO", ...}

# 4. abrir e concluir um plano de acao
curl -s -X POST "$BASE/api/v1/labs/groups/11/evidence/EVD-001025/action-plans" \
  -H "Content-Type: application/json" \
  -d '{"acao":"Atualizar procedimento e repetir a coleta.","prazo":"2026-08-26","responsavel":"owner.sistema.4"}'
# -> 201 {"id":"ACT-001025","status":"PENDENTE", ...}

curl -s -X POST "$BASE/api/v1/labs/groups/11/action-plans/ACT-001025/complete" \
  -H "Content-Type: application/json" \
  -d '{"conclusao":"Procedimento atualizado e evidencia coletada."}'
# -> 200 status passa a "CONCLUIDA"
```

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `RestoreEvidence` — 1.024 registros |
| Total do grupo | 3.481 registros em 4 tabelas |
| `email_id` | `EML-000001` — 1.024 e-mails |
| `evidence_id` | `EVD-000001` — 1.024 evidências |
| `IC` | `IC-000001` — **único** |
| `id` do registro | `REG-000001` — 1.024 linhas |
| `id` do plano de ação | `ACT-000004` — 409 planos |
| `ticket_mudanca` | `CHG-2001` a `CHG-2024` |
| `resultado` | `SUCESSO`, `PARCIAL`, `FALHA` |
| `sistema` | `erp`, `crm`, `billing`, `dw` |
| `severidade` | `ALTA`, `MEDIA`, `BAIXA` |
| `status` do registro | `EM_ANALISE`, `APROVADO`, `REPROVADO` |
| `status` do plano | `PENDENTE`, `CONCLUIDA` |
| `Content-Type` do download | `application/pdf` |

---

# Grupo 12 — Handover de modelos de ML

### Contexto de negócio

Um time de ML precisa entregar um modelo em produção. O handover passa por
validações automáticas — checksum do artefato, schema de features, documentação,
métricas e compliance — e só depois de aprovado o modelo é implantado, com
possibilidade de rollback. Este grupo **não expõe ground truth**: a validação é
pública, porque o exercício é justamente reprovar e corrigir a submissão.

### Base URL

```bash
https://tool-automation-fiap-production.up.railway.app/api/v1/labs/groups/12
```

### Variáveis

| Onde | Variável | Valores reais |
|---|---|---|
| path | `submission_id` | `SUB-000001` — 1.016 submissões |
| path | `artifact_id` | `ART-000001` |
| path | `deployment_id` | `DEP-000011` — 92 deploys |
| body/query | `modelo_id` | `mdl-000001` — **único**, repetir → 409 |
| query `GET /submissions` | `status` | `SUBMETIDO`, `APROVADO`, `DEPLOYADO` |
| query `GET /submissions` | `owner`, `framework` | `framework` ∈ `xgboost`, `pytorch`, `sklearn`, `lightgbm` |
| query `GET /submissions` | `target_env` | `DEV`, `STAGING`, `PROD` |
| query `GET /submissions` | `data_classificacao` | `PUBLICO`, `INTERNO`, `CONFIDENCIAL`, `RESTRITO` |
| query | `submission_id`, `model_id` | filtros das tabelas de apoio |
| query `GET /validation-results` | `status` | `PASS`, `FAIL`, `WARN` |
| body `POST /submissions` | `modelo_id`, `nome_modelo`, `version`, `owner`, `framework`, `target_env`, `data_classificacao` **obrigatórios** | — |
| body `POST /submissions` | `metrics` **obrigatório** | objeto, ex. `{"auc":0.91,"psi":0.05}` |
| body `POST /submissions` | `feature_schema` **obrigatório** | lista de objetos — **veja o aviso abaixo** |
| body `POST /submissions` | `model_card` **obrigatório** | objeto; usa `summary`, `intended_use`, `limitations`, `ethical_considerations`, `license`, `completeness` |
| body `POST /submissions` | `artifact_size_bytes` | padrão `512` |
| body demais POSTs | — | sem body |

> ⚠️ **Cada item de `feature_schema` precisa de `feature_name`, `dtype` e
> `nullable`.** O OpenAPI declara `feature_schema` como lista livre
> (`list[{}]`), então o Swagger não avisa — mas omitir `nullable` provoca
> **HTTP 500**. O mesmo vale para `dtype`. Veja o
> [Apêndice F](#apêndice-f--pendências-conhecidas).

### Endpoints

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/submissions` | Listar submissões de handover | não |
| `GET` | `/submissions/{submission_id}` | Obter uma submissão | não |
| `POST` | `/submissions` | Criar submissão com artefatos determinísticos | não |
| `POST` | `/submissions/{submission_id}/validate` | Executar todas as validações | não |
| `GET` | `/submissions/{submission_id}/validation-summary` | Resumo das validações | não |
| `POST` | `/submissions/{submission_id}/approve` | Aprovar quando as validações passam | não |
| `POST` | `/submissions/{submission_id}/deploy` | Implantar submissão aprovada | não |
| `GET` | `/submissions/{submission_id}/feature-schema` | Baixar schema de features (YAML) | não |
| `GET` | `/submissions/{submission_id}/metrics` | Baixar métricas (JSON) | não |
| `GET` | `/submissions/{submission_id}/model-card` | Baixar model card (Markdown) | não |
| `GET` | `/submissions/{submission_id}/artifacts/{artifact_id}/download` | Baixar artefato binário | não |
| `GET` | `/artifacts` | Listar artefatos de modelo | não |
| `GET` | `/metrics` | Listar métricas | não |
| `GET` | `/model-cards` | Listar model cards | não |
| `GET` | `/validation-results` | Listar resultados de validação | não |
| `GET` | `/feature-schema` | Listar schema de features | não |
| `GET` | `/jira-tickets` | Listar tickets Jira | não |
| `GET` | `/model-notifications` | Listar notificações do modelo | não |
| `GET` | `/deployments` | Listar deploys | não |
| `POST` | `/deployments/{deployment_id}/rollback` | Reverter um deploy | não |
| `GET` | `/model-stats` | Agregados de handover | não |

**Total: 21 operações.**

### Como utilizar a API

**GET — submissões, validações e artefatos**

```bash
curl -s "$BASE/api/v1/labs/groups/12/submissions?limit=2"
curl -s "$BASE/api/v1/labs/groups/12/submissions?status=SUBMETIDO&framework=xgboost"
curl -s "$BASE/api/v1/labs/groups/12/submissions/SUB-000001"

# resumo das validacoes
curl -s "$BASE/api/v1/labs/groups/12/submissions/SUB-000001/validation-summary"
curl -s "$BASE/api/v1/labs/groups/12/validation-results?submission_id=SUB-000001&status=FAIL"

# tabelas de apoio
curl -s "$BASE/api/v1/labs/groups/12/artifacts?submission_id=SUB-000001"
curl -s "$BASE/api/v1/labs/groups/12/metrics?submission_id=SUB-000001"
curl -s "$BASE/api/v1/labs/groups/12/feature-schema?submission_id=SUB-000001"
curl -s "$BASE/api/v1/labs/groups/12/model-cards?model_id=mdl-000001"
curl -s "$BASE/api/v1/labs/groups/12/deployments?model_id=mdl-000011"
curl -s "$BASE/api/v1/labs/groups/12/jira-tickets?submission_id=SUB-000011"
curl -s "$BASE/api/v1/labs/groups/12/model-notifications?submission_id=SUB-000011"
curl -s "$BASE/api/v1/labs/groups/12/model-stats"

# BAIXAR os artefatos (use -OJ, nao res.json())
curl -sOJ "$BASE/api/v1/labs/groups/12/submissions/SUB-000001/feature-schema"
curl -sOJ "$BASE/api/v1/labs/groups/12/submissions/SUB-000001/metrics"
curl -sOJ "$BASE/api/v1/labs/groups/12/submissions/SUB-000001/model-card"
curl -sOJ "$BASE/api/v1/labs/groups/12/submissions/SUB-000001/artifacts/ART-000001/download"
```

**POST — submissão, validação, aprovação e deploy**

```bash
# 1. criar a submissao (modelo_id inedito; capture o submission_id)
curl -s -X POST "$BASE/api/v1/labs/groups/12/submissions" \
  -H "Content-Type: application/json" -H "X-Lab-Group: grupo-alfa" \
  -d '{
        "modelo_id":"mdl-999999",
        "nome_modelo":"Modelo 999999",
        "version":"9.9.9",
        "owner":"team-99",
        "framework":"xgboost",
        "target_env":"PROD",
        "data_classificacao":"PUBLICO",
        "metrics":{"auc":0.91,"psi":0.05},
        "feature_schema":[
          {"feature_name":"idade","dtype":"int","nullable":false,"min_value":0,"max_value":100}
        ],
        "model_card":{
          "summary":"Modelo para apoio a decisao.",
          "intended_use":"Priorizacao operacional.",
          "limitations":"Nao usar como criterio unico.",
          "ethical_considerations":"Monitorar drift.",
          "license":"interna",
          "completeness":90
        }
      }'
# -> 201 {"submission_id":"SUB-001017","status":"SUBMETIDO", ...}
# -> 409 {"detail":"modelo_id already exists"} se o modelo ja foi submetido

# 2. validar (capture o submission_id da resposta anterior)
curl -s -X POST "$BASE/api/v1/labs/groups/12/submissions/SUB-001017/validate" \
  -H "Content-Type: application/json"
# -> 200 {"submission_id":"SUB-001017","overall_status":"PASS","checks":[...]}

# 3. aprovar e implantar
curl -s -X POST "$BASE/api/v1/labs/groups/12/submissions/SUB-001017/approve" \
  -H "Content-Type: application/json"
# -> 200 status passa a "APROVADO"

curl -s -X POST "$BASE/api/v1/labs/groups/12/submissions/SUB-001017/deploy" \
  -H "Content-Type: application/json"
# -> 200 {"id":"DEP-001013","model_id":"mdl-999999","environment":"PROD",
#          "status":"CONCLUIDO","replicas":2, ...}

# 4. reverter um deploy (o rollback mira um deploy existente, nao a submissao)
curl -s -X POST "$BASE/api/v1/labs/groups/12/deployments/DEP-000011/rollback" \
  -H "Content-Type: application/json"
# -> 200 status passa a "ROLLBACK"
```

### IDs, enums e volumes

| Item | Valor |
|---|---|
| Tabela principal | `ModelSubmission` — 1.016 registros |
| Total do grupo | 17.548 registros em 9 tabelas |
| `submission_id` | `SUB-000001` |
| `modelo_id` | `mdl-000001` — **único** |
| `id` do artefato | `ART-000001` — 1.016 artefatos |
| `id` da métrica | `MET-000001-auc` — 5.080 métricas |
| `id` do schema | `SCH-000001-1` — 3.048 features |
| `id` do model card | `CRD-000001` — 1.016 cards |
| `id` da validação | `VAL-000001-BIAS` — 6.096 resultados |
| `id` do deploy | `DEP-000011` — 92 deploys |
| `id` do ticket Jira | `JIR-000011` — 92 tickets, `key` `ML-2011` |
| `id` da notificação | `NTF-000011` — 92 notificações |
| `status` da submissão | `SUBMETIDO`, `APROVADO`, `DEPLOYADO` |
| `framework` | `xgboost`, `pytorch`, `sklearn`, `lightgbm` |
| `target_env` | `DEV`, `STAGING`, `PROD` |
| `data_classificacao` | `PUBLICO`, `INTERNO`, `CONFIDENCIAL`, `RESTRITO` |
| `metric_name` | `auc` (threshold 0.70), `psi` (threshold 0.20), outras (0.65) |
| `check_name` | `CHECKSUM`, `SCHEMA`, `DOCS`, `METRICS`, `BIAS`, `COMPLIANCE` |
| `status` da validação | `PASS`, `FAIL`, `WARN` |
| `Content-Type` dos downloads | `application/yaml`, `application/json`, `text/markdown`, `application/octet-stream` |

---

# Apêndice A — Endpoints de plataforma

Independentes do grupo. Úteis para descobrir o que existe.

| Método | Path | Descrição | Instrutor |
|---|---|---|---|
| `GET` | `/api/v1/labs/meta` | Metadados, cenários e convenções | não |
| `GET` | `/api/v1/labs/groups` | Grupos e contagem de registros | não |
| `GET` | `/api/v1/labs/groups/{group_id}/models` | Tabelas registradas no grupo | não |
| `GET` | `/api/v1/labs/groups/{group_id}/integrity` | Integridade referencial | **sim** |
| `POST` | `/api/v1/labs/reset` | Purga e re-semeia deterministicamente | **sim** |

```bash
# grupos e o que já está semeado
curl -s "$BASE/api/v1/labs/groups"
# -> {"total_groups":12,"min_records_per_group":1000,"seed":2026,
#     "reference_date":"2026-09-13","groups":[{"group_id":"01","slug":"prospeccao-leads",
#         "title":"Prospecao e qualificacao de leads","seeded":true,"total_records":1122, ...}, ...]}

# tabelas de um grupo
curl -s "$BASE/api/v1/labs/groups/08/models"

# integridade referencial (exige chave de instrutor)
curl -s -H "X-Instructor-Key: $KEY" "$BASE/api/v1/labs/groups/10/integrity"
# -> {"group_id":"10","seeded":true,"checked_relations":6,"violations":[],"healthy":true}
```

---

# Apêndice B — Downloads binários

Seis endpoints devolvem arquivo em vez do envelope JSON. **Não use
`res.json()`** nesses endpoints — use `curl -OJ`.

| Grupo | Endpoint | `Content-Type` |
|---|---|---|
| 02 | `GET /files/{file_id}/download` | `…officedocument.spreadsheetml.sheet` (XLSX) |
| 11 | `GET /evidence/{evidence_id}/pdf` | `application/pdf` |
| 12 | `GET /submissions/{submission_id}/feature-schema` | `application/yaml` |
| 12 | `GET /submissions/{submission_id}/model-card` | `text/markdown` |
| 12 | `GET /submissions/{submission_id}/metrics` | `application/json` |
| 12 | `GET /submissions/{submission_id}/artifacts/{artifact_id}/download` | `application/octet-stream` |

O `Content-Disposition` suggestivo faz o `-OJ` gravar com o nome sugerido pelo
servidor. Os artefatos são determinísticos: o mesmo id devolve sempre os mesmos
bytes, o que permite comparar checksums entre execuções.

Nomes de arquivo devolvidos para `SUB-000001`:

| Endpoint | `Content-Disposition` |
|---|---|
| `/feature-schema` | `mdl-000001-schema.yaml` |
| `/metrics` | `SUB-000001-metrics.json` |
| `/model-card` | `mdl-000001-model-card.md` |
| `/artifacts/ART-000001/download` | `mdl-000001-2.1.1.bin` |

---

# Apêndice C — Endpoints de instrutor

Onze operações exigem a chave de instrutor. Nove revelam a resposta correta do
exercício; as outras duas são utilitários de manutenção. O grupo 12 não expõe
ground truth.

| Grupo | Endpoint | O que revela |
|---|---|---|
| 01 | `GET /instructor/leads/{lead_id}` | lead com o label de ground truth |
| 01 | `POST /instructor/leads/{lead_id}/classify` | label do modelo para comparação |
| 04 | `GET /instructor/customer-events/{event_id}` | intenção e confiança ocultas |
| 05 | `GET /instructor/messages/{message_id}` | intenção real da mensagem |
| 07 | `GET /instructor/receivables/{receivable_id}` | decisão de cobrança esperada |
| 08 | `GET /instructor/unlock-requests/{request_id}` | decisão de desbloqueio esperada |
| 09 | `GET /instructor/candidates/{candidate_id}` | ground truth do candidato |
| 10 | `GET /instructor/patient-messages/{message_id}` | campos de classificação ocultos |
| 11 | `GET /instructor/evidence/{evidence_id}` | ground truth da evidência |
| todos | `GET /groups/{group_id}/integrity` | integridade referencial |
| todos | `POST /api/v1/labs/reset` | purga e re-semeia |

> **Sem `LABS_INSTRUCTOR_KEY` configurada, todos respondem 403.** Esse é o estado
> atual de produção. Para habilitar:
> `railway variables --set "LABS_INSTRUCTOR_KEY=<uma-chave-forte>"`, reiniciar o
> serviço e enviar `X-Instructor-Key: <a-chave>`.

---

# Apêndice D — Volumes por grupo

Todo grupo tem ao menos 1.000 registros na tabela principal. Os números são
determinísticos: com `LABS_SEED=2026` e `LABS_TODAY=2026-09-13`, o mesmo seed
produz exatamente as mesmas contagens.

Duas métricas, e elas não são o mesmo número:

- **Principal** — registros da tabela que o grupo ensina a manipular.
- **Total** — soma de todas as tabelas do grupo, incluindo as auxiliares. É o
  valor que aparece em `total_records` de `GET /api/v1/labs/groups`.

| Grupo | Slug | Tabela principal | Principal | Total | Modelos | Operações |
|---|---|---|---:|---:|---:|---:|
| 01 | `prospeccao-leads` | `Lead` | 1.084 | 1.122 | 4 | 11 |
| 02 | `ingestao-taxas` | `PrimaryMarketRate` | 1.176 | 1.205 | 3 | 6 |
| 03 | `revops-bitrix` | `Opportunity` | 1.152 | 4.440 | 9 | 12 |
| 04 | `atendimento-multicanal` | `CustomerEvent` | 1.144 | 1.152 | 2 | 8 |
| 05 | `pos-venda-ecommerce` | `Ticket` | 1.140 | 4.866 | 6 | 14 |
| 06 | `purchase-order` | `PurchaseOrder` | 1.120 | 5.822 | 7 | 18 |
| 07 | `cobranca-financeira` | `Receivable` | 1.150 | 1.450 | 3 | 11 |
| 08 | `desbloqueio-confianca` | `UnlockRequest` | 1.110 | 6.391 | 6 | 14 |
| 09 | `onboarding-rh` | `Candidate` | 1.032 | 14.792 | 6 | 15 |
| 10 | `clinica-agendamentos` | `Appointment` | 1.048 | 4.598 | 7 | 19 |
| 11 | `evidencias-restore` | `RestoreEvidence` | 1.024 | 3.481 | 4 | 15 |
| 12 | `handover-modelos-ml` | `ModelSubmission` | 1.016 | 17.548 | 9 | 21 |
| | | | | | **164** | |

> Snapshot de 26/09/2026: em produção, os grupos **01, 02, 03, 05, 07, 08 e
> 10** estavam semeados; **04, 06, 09, 11 e 12** reportavam zero até a primeira
> visita. Esse estado muda conforme o uso — trate `total_records` como "o que
> existe agora", não como "o que virá".

---

# Apêndice E — Caminhos compartilhados entre grupos

Os 12 grupos dividem o prefixo `/api/v1/labs/groups/{group_id}`. Por isso,
recursos de mesmo nome lógico recebem sufixos distintos. Duas rotas são
registradas em um único módulo, mas respondem por **dois** grupos, decidido pelo
`{group_id}` da URL:

| Rota | Se o `{group_id}` for… | O que devolve |
|---|---|---|
| `GET /stats` | `05` | agregados de mensagens, tickets por prioridade e status |
| `GET /stats` | `08` | agregados de solicitações por status e decisões por tipo |
| `GET /stats` | qualquer outro | **404** |
| `GET /history` | `07` | histórico de cobrança (`HIS-*`) |
| `GET /history` | `08` | histórico de desbloqueio (`UHI-*`) |
| `GET /history` | qualquer outro | **404** |

No grupo 08, cada par tem uma rota própria equivalente:

| Grupo 08 | Path próprio | Rota compartilhada | Situação |
|---|---|---|---|
| agregados | `GET /unlock-stats` | `GET /stats` | própria em produção |
| histórico | `GET /unlock-history` | `GET /history` | própria já em produção |

Os demais paths com sufixo de grupo: `/patient-messages` (10),
`/clinic-stats` (10), `/onboarding-stats` (09), `/evidence-stats` (11),
`/model-stats` (12), `/model-notifications` (12), `/notifications` (06).

**Consulte sempre o Swagger do grupo antes de adivinhar o path.**

---

# Apêndice F — Pendências conhecidas

| # | Onde | Sintoma | Impacto |
|---|---|---|---|
| 1 | `POST /api/v1/labs/groups/11/emails/{email_id}/evidence` | Enviar um `IC` já existente responde **500** em vez de **409** | `IC` tem restrição `UNIQUE` no banco e o handler não trata `IntegrityError`. Use sempre um `IC` inédito |
| 2 | `POST /api/v1/labs/groups/12/submissions` | `feature_schema` sem `nullable` (ou sem `dtype`) em cada item responde **500** | O OpenAPI declara `feature_schema` como `list[{}]`, então o Swagger não avisa. Sempre envie `feature_name`, `dtype` e `nullable` |
| 3 | Configuração Railway | `ENVIRONMENT=development` e `DATABASE_URL` em SQLite sem volume confirmado | Ver [0.9](#09-variáveis-de-ambiente-em-produção) |

Os itens 1 e 2 são defeitos de tratamento de erro (exceções de integridade de
dado não tratadas viram 500 em vez de 4xx), não problemas de contrato. As 169
operações de labs deste guia já respondem em produção.

---

# Apêndice G — Ao adicionar um endpoint

Para não reintroduzir ambiguidade de rota:

1. **Verifique se o path já existe em outro grupo.** Os 12 dividem o mesmo
   prefixo; um nome repetido colide. Use um sufixo específico
   (Apêndice E).
2. **Dê um `operation_id` único**, no formato `labs_groupNN_<acao>`.
3. **Respeite o envelope de paginação** em listagens.
4. **Aceite `?scenario=`** para que o exercício de tratamento de erro funcione.
5. **Trate `IntegrityError` como 409**, nunca como 500 — um payload inválido é
   erro do cliente (Apêndice F, itens 3 e 4).
6. **Mantenha o registro em `docs/openapi.yaml` e na coleção Postman** em dia —
   regere com os scripts do Apêndice H.
7. **Atualize este arquivo** com o novo endpoint.

---

# Apêndice H — Ferramentas de apoio

| Recurso | Caminho |
|---|---|
| Coleção Postman | `postman/Quantum-Commerce-API.postman_collection.json` — pasta `Workflow Labs` com 169 requests. Os 45 requests originais da API foram preservados. |
| OpenAPI estático | `docs/openapi.yaml` |
| Guia dos labs | `docs/student-workflow-labs.md` |
| Gerar artefatos | `python scripts/export_openapi.py` · `python scripts/export_labs_postman.py` |

A coleção Postman usa as variáveis `baseUrl` e `instructorKey`, ambas em
`postman/Quantum-Commerce-API.postman_environment.json`. Aponte `baseUrl` para a
URL de produção e preencha `instructorKey` se habilitar a chave de instrutor.
