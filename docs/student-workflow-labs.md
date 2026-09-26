# Guia dos Laboratorios de Workflow

Os 12 laboratorios vivem sob o prefixo `/api/v1/labs` e compartilham as mesmas
convencoes. Este guia explica as convencoes uma vez e depois lista o que cada
grupo practice.

> Todos os dados sao ficticios e gerados de forma deterministica. Nao ha dado
> real de clientes, empresas ou pessoas.

## 1. Subindo o ambiente

```bash
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger em `http://localhost:8000/docs`, colecao Postman em
`postman/Quantum-Commerce-API.postman_collection.json` (pasta `Workflow Labs`).

Os seeds dos laboratorios sao **lazy**: o grupo so e populado no primeiro
acesso a um endpoint dele. Nao ha seed de 12 grupos no boot.

## 2. Convencoes globais

| Item | Valor |
|------|-------|
| Prefixo | `/api/v1/labs` |
| Semente | `LABS_SEED=2026` |
| Data de referencia | `LABS_TODAY=2026-09-13` |
| Volume minimo por grupo | 1000 registros na tabela principal |
| Identificador de grupo | `1`-`12`, `01`-`12` ou `group-1`-`group-12` |
| Envelope de listagem | `{"items": [...], "meta": {...}}` |
| Limite de pagina | `limit` entre 1 e 200 (padrao 20) |

`meta` traz `total`, `limit`, `offset`, `total_pages` e `has_more`, o que
permite paginar sem adivinar quando a ultima pagina esta cheia.

### Determinismo

Dois resets seguidos produzem exatamente os mesmos dados. Isso permite
trabalhar com IDs, ordenacoes e comparacoes sem surpresa:

```bash
curl -X POST http://localhost:8000/api/v1/labs/reset \
  -H 'Content-Type: application/json' -H 'X-Instructor-Key: chave-de-instrutor' \
  -d '{"groups":[1]}'
```

Nenhuma automacao deve confiar em `datetime.now()`, `random` sem semente ou
`uuid4()`. Timestamps respeitam `created <= updated` e nunca passam de
`2026-09-13 23:59:59`.

### Injeccao de falhas

Todo endpoint aceita o query param `scenario`:

| Valor | Resposta esperada |
|-------|-------------------|
| `success` (ou ausente) | fluxo normal |
| `validation_error` | `422` |
| `not_found` | `404` |
| `duplicate` | `409` |
| `timeout` | `504` |
| `server_error` | `500` |

```bash
curl 'http://localhost:8000/api/v1/labs/groups/01/leads?scenario=duplicate'
```

Valor desconhecido devolve `422` com a lista de valores suportados. O
parametro funciona tambem em leituras (`GET`), nao apenas em escritas.

### Ordenacao e filtros

Listagens aceitam `sort` e `order` (`asc`/`desc`). Campo inexistente devolve
`400`. Filtros de texto usam busca parcial, combinando com paginacao.

### Idempotencia

Endpoints de criacao que exigem `Idempotency-Key` devolvem o recurso ja
existente quando a mesma chave repete a requisicao, em vez de duplicar. Reenvio
com a mesma chave e payload diferente devolve `409`. Isso e o que diferencia uma
automacao segura de uma automacao que duplica pedidos a cada retry.

### Integridade referencial

Os laboratorios nao usam chaves estrangeiras: a integridade e garantida pelos
seeds e verificada por endpoint.

```bash
curl -H 'X-Instructor-Key: chave-de-instrutor' \
  http://localhost:8000/api/v1/labs/groups/01/integrity
```

A resposta traz `healthy` e `violations`. Se aparecer violacao, o seed foi
alterado por fora do fluxo oficial.

### Respostas de instrutor e ground truth

Alguns exercicios tem uma resposta certa (categoria esperada, decisao de
aprovacao, divergencia detectada). Esses campos **nunca** aparecem nas respostas
de aluno. ficam em `/instructor/...`, que exigem o header `X-Instructor-Key`:

```bash
curl -H 'X-Instructor-Key: chave-de-instrutor' \
  http://localhost:8000/api/v1/labs/groups/01/instructor/leads/1
```

Sem o header: `401`. Com header errado: `401`. Sem `LABS_INSTRUCTOR_KEY`
configurada no ambiente: `403`. O objetivo e que a automacao do aluno nunca
consiga "adivinhar" a resposta lendo o payload.

### Auditoria

Mutacoes gravam evento em `api/app/events` com `event_type`, `lab_group`,
`resource_type`, `resource_id` e `metadata`. Consultavel em
`GET /api/v1/events?event_type=...`.

## 3. Endpoints de plataforma

| Metodo | Caminho | Descricao |
|--------|---------|-----------|
| GET | `/api/v1/labs/meta` | convencoes, seed, data de referencia, cenarios suportados |
| GET | `/api/v1/labs/groups` | os 12 grupos, se estao populados e o total de registros |
| GET | `/api/v1/labs/groups/{group_id}/models` | tabelas, colunas e relacoes do grupo |
| GET | `/api/v1/labs/groups/{group_id}/integrity` | violacoes de integridade (instrutor) |
| POST | `/api/v1/labs/reset` | reseed deterministico (instrutor) |

`POST /api/v1/labs/reset` aceita `{"groups": [1, 2]}`. Com `{"groups": null}`
ou corpo vazio, reseta todos os grupos. Grupos que nao estao disponiveis no
ambiente aparecem em `skipped_groups` em vez de quebrar a chamada.

## 4. Os 12 grupos

| Grupo | slug | Modelos | Foco |
|-------|------|---------|------|
| 01 | `prospeccao-leads` | Lead, SalesRep, Campaign, Product | captura, dedupe, atribuicao, qualificacao |
| 02 | `ingestao-taxas` | PrimaryMarketRate, IngestionFile, IndexerMapping | planilha XLSX, CNPJ, vencimento, indexador |
| 03 | `revops-bitrix` | Load, Opportunity, CrmUser, CrmContact, CrmDeal, ... | texto livre para Deals e contatos |
| 04 | `atendimento-multicanal` | CustomerEvent, Department | intencao, prioridade, SLA, roteamento |
| 05 | `pos-venda-ecommerce` | Message, Customer, Order, Shipment, Ticket, ... | intencao pos-venda, busca por CPF/telefone |
| 06 | `purchase-order` | EmailRequest, PurchaseRequest, Vendor, Budget, PurchaseOrder, ... | extracao de e-mail, budget, aprovacao |
| 07 | `cobranca-financeira` | Receivable, CollectionHistory, CollectionConfig | faixas de atraso, decisao de envio, baixa |
| 08 | `desbloqueio-confianca` | UnlockRequest, CustomerContract, Invoice, CreditCheck, ... | promessa de pagamento, credito, provisionamento |
| 09 | `onboarding-rh` | Candidate, Onboarding, AccessMatrix, Equipment, ... | aprovacao de acessos, excecoes de admissao |
| 10 | `clinica-agendamentos` | Appointment, PatientMessage, PatientMessageLabel, Slot, Waitlist, ... | confirmacao e remarcacao por WhatsApp |
| 11 | `evidencias-restore` | IncomingEmail, RestoreEvidence, EvidenceRegistry, ActionPlan | evidencia PDF, divergencia, plano de acao |
| 12 | `handover-modelos-ml` | ModelSubmission, ModelArtifact, Metrics, ModelCard, ... | checksum, schema, metricas, compliance, deploy |

Detalhes de cada grupo estao no Swagger, na pasta `Workflow Labs` do Postman e
na docstring dos proprios endpoints.

### Paths especificos por grupo

Cada grupo expoe seus recursos sob nomes proprios. Alguns recursos aparecem em
varios grupos com o mesmo nome logico (`messages`, `stats`, `history`,
`notifications`); como todos compartilham o prefixo
`/api/v1/labs/groups/{group_id}`, o sufixo precisa ser unico para o roteamento
nao ficar ambiguo:

| Path | Grupos que usam |
|------|-----------------|
| `/messages` | 05 |
| `/patient-messages` | 10 |
| `/stats` | 05 |
| `/clinic-stats` | 10 |
| `/unlock-stats` | 08 |
| `/onboarding-stats` | 09 |
| `/evidence-stats` | 11 |
| `/model-stats` | 12 |
| `/history` | 07 |
| `/unlock-history` | 08 |
| `/notifications` | 06 |
| `/model-notifications` | 12 |

Use sempre o Swagger do grupo para descobrir o path exato.

## 5. Artefatos binarios

Alguns grupos entregam arquivos de verdade, nao JSON:

| Grupo | Endpoint | Tipo |
|-------|----------|------|
| 02 | `GET /files/{file_id}/download` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| 11 | `GET /evidence/{evidence_id}/pdf` | `application/pdf` |
| 12 | `GET /submissions/{id}/artifacts/{artifact_id}/download` | varia por artifact |

Todos sao byte-deterministas: a mesma entrada devolve sempre os mesmos bytes.
Para automatizar um check de integridade, compare `Content-Length` ou o hash
SHA-256 em duas chamadas, e nao o conteudo visual.

## 6. Rodando os testes

```bash
cd api
../.venv/bin/python -m pytest -q
```

A suite original da Quantum Commerce continua intacta. Os testes dos labs estao
em `tests/test_labs_*.py` e cobrem volume, paginacao, aliases de grupo,
determinismo, cenarios de falha, integridade e ausencia de ground truth em
payload de aluno.

Para regenerar a pasta `Workflow Labs` do Postman depois de mudar rotas:

```bash
python scripts/export_labs_postman.py
```
