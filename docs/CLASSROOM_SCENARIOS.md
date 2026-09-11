# Classroom Scenarios: FIAP Student Desk Lab

Este documento contém cenários didáticos para exercícios de classificação, busca em base de conhecimento e automação de solicitações.

## Como usar
Cada cenário representa uma interação de um aluno. Os alunos devem configurar seus workflows para processar essas mensagens e chegar ao resultado esperado.

> **Nota:** Os campos "esperados" são referências pedagógicas. O comportamento real do LLM pode variar.

## Cenários de Exercício

| # | Mensagem do Aluno | student_id | Categoria | Intenção | Impacto/Urgência | Auto-resposta? | Artigo KB | Criar Request? | Depto |
|---|-------------------|------------|-----------|----------|------------------|----------------|-----------|----------------|-------|
| 01 | "Não consigo acessar o ambiente para enviar meu projeto" | STU001 | digital_learning | report_problem | high/high | Sim | KB001 | Não | Tecnologia Educacional |
| 02 | "Preciso de uma declaração de matrícula para o estágio" | STU002 | academic_services | request_document | medium/low | Não | KB002 | Sim | Secretaria Acadêmica |
| 03 | "Minha mensalidade está com valor diferente do contrato" | STU003 | finance | financial_question | medium/medium | Não | KB003 | Sim | Financeiro |
| 04 | "Quero saber como funciona o programa de estágios" | STU004 | career | career_question | low/low | Sim | KB004 | Não | Carreiras |
| 05 | "Meu acesso ao laboratório físico não está funcionando" | STU005 | campus_access | report_problem | high/medium | Sim | KB005 | Não | Infraestrutura |
| 06 | "Como faço para trancar uma disciplina?" | STU006 | academic_services | ask_question | low/medium | Sim | KB006 | Não | Secretaria Acadêmica |
| 07 | "Esqueci minha senha do e-mail institucional" | STU007 | digital_learning | report_problem | medium/high | Sim | KB007 | Não | TI Suporte |
| 08 | "Onde vejo o calendário de provas do semestre?" | STU008 | academic_services | ask_question | low/low | Sim | KB008 | Não | Secretaria Acadêmica |
| 09 | "Recebi uma cobrança indevida de biblioteca" | STU009 | finance | financial_question | low/medium | Não | KB009 | Sim | Financeiro |
| 10 | "Quero atualizar meu endereço no cadastro" | STU010 | academic_services | report_problem | low/low | Não | KB010 | Sim | Secretaria Acadêmica |
| 11 | "O Wi-Fi do campus está muito lento hoje" | STU011 | campus_access | report_problem | medium/medium | Sim | KB011 | Não | TI Suporte |
| 12 | "Preciso de ajuda com o conteúdo da aula de Python" | STU012 | digital_learning | ask_question | low/low | Sim | KB012 | Não | Tutoria |
| 13 | "Como solicito o passe escolar (SPTrans)?" | STU013 | academic_services | request_document | low/medium | Sim | KB013 | Não | Secretaria Acadêmica |
| 14 | "Quero saber sobre bolsas de estudo por mérito" | STU014 | finance | ask_question | low/low | Sim | KB014 | Não | Financeiro |
| 15 | "Minha nota da prova não aparece no portal" | STU015 | academic_services | report_problem | medium/medium | Não | KB015 | Sim | Secretaria Acadêmica |
| 16 | "Onde fica a sala de inovação no campus Paulista?" | STU016 | campus_access | ask_question | low/low | Sim | KB016 | Não | Infraestrutura |
| 17 | "Quero me inscrever no hackathon da FIAP" | STU017 | career | ask_question | low/low | Sim | KB017 | Não | Eventos |
| 18 | "Não recebi o link para a aula síncrona de hoje" | STU018 | digital_learning | report_problem | high/high | Sim | KB018 | Não | Tecnologia Educacional |
| 19 | "Como faço para validar horas complementares?" | STU019 | academic_services | ask_question | low/low | Sim | KB019 | Não | Secretaria Acadêmica |
| 20 | "Perdi meu cartão de acesso ao prédio" | STU020 | campus_access | report_problem | medium/medium | Não | KB020 | Sim | Segurança |
| 21 | "Quero saber se a biblioteca abre aos sábados" | STU021 | campus_access | ask_question | low/low | Sim | KB021 | Não | Biblioteca |
| 22 | "Meu boleto venceu e não consigo gerar a segunda via" | STU022 | finance | financial_question | medium/high | Sim | KB022 | Não | Financeiro |
| 23 | "Como acesso o portal de vagas da FIAP?" | STU023 | career | ask_question | low/low | Sim | KB023 | Não | Carreiras |
| 24 | "O software do laboratório de redes está dando erro" | STU024 | digital_learning | report_problem | medium/medium | Sim | KB024 | Não | TI Suporte |
| 25 | "Preciso de um histórico escolar oficial" | STU025 | academic_services | request_document | medium/low | Não | KB025 | Sim | Secretaria Acadêmica |
| 26 | "Quero saber sobre o intercâmbio para o Canadá" | STU026 | career | ask_question | low/low | Sim | KB026 | Não | Internacional |

## Discussão em Aula
- **Cenários 01 e 18:** Alta urgência. O workflow deve priorizar a resposta ou o encaminhamento imediato.
- **Cenários 02, 03, 09, 15, 20, 25:** Exigem criação de solicitação (Request) pois envolvem documentos oficiais, dinheiro ou segurança física.
- **Cenários de Auto-resposta:** O desafio é garantir que o LLM não invente informações (alucinação) e use apenas a base de conhecimento.
- **Cenários de Erro:** Como o workflow deve se comportar se a API de busca de conhecimento estiver fora do ar?
