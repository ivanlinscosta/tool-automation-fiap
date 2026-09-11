# FIAP Student Desk Lab API

## Visão Geral
Esta API é o componente de execução do laboratório de automação. Ela gerencia dados de alunos, base de conhecimento, solicitações acadêmicas e auditoria.

## Principais Funcionalidades
- **Gestão de Alunos:** Consulta de dados cadastrais.
- **Base de Conhecimento:** Busca semântica de artigos para RAG.
- **Motor de Prioridade:** Cálculo determinístico de SLA.
- **Workflow de Solicitações:** Criação, atualização e aprovação de pedidos.
- **Simulador de Falhas:** Endpoints específicos para treinar resiliência em workflows.

## Como Começar

1. **Instalação:** Siga as instruções no [README.md](../README.md) principal.
2. **Exploração:** Use o Swagger em `http://localhost:8000/docs` para testar os endpoints manualmente.
3. **Integração:** Importe o `openapi.json` no n8n, Make ou Dify.

## Estrutura de Dados
A API utiliza SQLite para persistência local. Os dados são isolados pelo header `X-Student-ID`.

## Documentação Técnica
- [Contratos da API](API_CONTRACTS.md)
- [Arquitetura do Sistema](ARCHITECTURE.md)
- [Cenários de Teste](CLASSROOM_SCENARIOS.md)

> **Aviso:** Este é um projeto didático. Não utilize dados reais ou sensíveis.
