# Case Study: FIAP Student Desk Lab
## Central Inteligente de Solicitações Acadêmicas

> **Aviso:** Este projeto é um laboratório educacional fictício e não representa sistemas ou políticas oficiais da FIAP. Todo o conteúdo é criado para fins didáticos.

### Contexto
Os alunos da FIAP enviam diariamente diversas dúvidas e solicitações sobre a vida acadêmica, desde problemas técnicos no ambiente virtual até pedidos de documentos e questões financeiras. Atualmente, o volume de mensagens é alto e o processamento manual gera atrasos.

### Problema
A classificação manual e o roteamento de solicitações consomem muito tempo. Muitas dúvidas são repetitivas e poderiam ser respondidas automaticamente se houvesse uma integração eficiente entre a comunicação do aluno, uma base de conhecimento e os sistemas internos.

### Objetivo
Demonstrar como a automação utilizando LLMs (Large Language Models) integrada a APIs REST pode transformar o atendimento ao aluno, proporcionando respostas rápidas e precisas, além de organizar solicitações complexas para aprovação humana.

### Workflow do Laboratório
1. **Webhook:** Recebe a mensagem do aluno (student_id + message).
2. **Identify:** Busca os dados do aluno na API para personalizar o atendimento.
3. **Classify:** O LLM analisa a mensagem e extrai categoria, intenção, impacto e urgência.
4. **Search:** O workflow busca na Base de Conhecimento (Knowledge Base) artigos relacionados à dúvida.
5. **Decide:** 
   - Se o LLM encontrar uma resposta clara na base de conhecimento, ele gera uma resposta fundamentada (Grounded Response).
   - Se a dúvida exigir ação humana ou não houver informação na base, o workflow cria uma solicitação formal (Request).
6. **Approval:** Solicitações críticas passam por um fluxo de aprovação humana.
7. **Audit:** Todas as ações são registradas para auditoria e melhoria contínua.

### Objetivos Pedagógicos
- Praticar o uso de Webhooks e APIs REST.
- Manipular dados em formato JSON.
- Integrar LLMs em fluxos de trabalho (Workflows).
- Implementar saídas estruturadas (Structured Output) com LLMs.
- Explorar RAG (Retrieval Augmented Generation) e Tool Calling.
- Implementar tratamento de erros, retentativas e limites de taxa (Rate Limiting).

### Arquitetura: Cognição vs Execução
Neste laboratório, separamos claramente as responsabilidades:
- **Cognição (LLM):** Responsável por entender a linguagem natural, classificar intenções e gerar respostas. O LLM reside no Workflow (n8n/Make/Dify).
- **Execução (API):** Responsável por fornecer dados, gerenciar a base de conhecimento, calcular prioridades e persistir solicitações. A API é o "sistema de registro".

### Disclaimer
Todo o conteúdo, incluindo nomes de alunos, departamentos e artigos de conhecimento, é fictício e criado exclusivamente para fins educacionais na disciplina de Tools, Automations and Workflows.
