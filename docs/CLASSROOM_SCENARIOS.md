# Classroom Scenarios

## Como usar

Os cenários abaixo servem para exercícios de classificação, roteamento, priorização e abertura de tickets na FlowDesk Lab API.

> `categoria`, `impact`, `urgency` e `priority` abaixo representam **resultado pedagógico esperado**. Em fluxos com LLM, o resultado não é garantido e pode variar conforme prompt, contexto e estratégia de parsing.

## Cenários

| # | Título | employee_id | mensagem | categoria esperada | impact esperado | urgency esperada | priority esperada |
|---|--------|-------------|----------|--------------------|-----------------|------------------|-------------------|
| 01 | Notebook sem Wi-Fi | EMP012 | Meu notebook conectou na rede da empresa, mas não abre nada e preciso enviar atividades agora. | it | medium | high | high |
| 02 | Phishing email received | EMP006 | Recebi um e-mail pedindo minha senha corporativa e cliquei no link sem querer. | security | high | high | critical |
| 03 | Reembolso pendente | EMP003 | Enviei meu reembolso de viagem faz duas semanas e ainda não apareceu no sistema. | finance | low | medium | low |
| 04 | Documento RH | EMP004 | Preciso de uma segunda via da carta de comprovação de vínculo para resolver um assunto pessoal. | hr | low | low | low |
| 05 | Ar-condicionado no escritório | EMP015 | O ar-condicionado da sala está quebrado e a equipe inteira está desconfortável desde ontem. | facilities | medium | medium | medium |
| 06 | Solicitação ambígua | EMP008 | Não consigo resolver um problema com meu cadastro interno e ninguém sabe dizer se é sistema ou processo. | other | low | medium | low |
| 07 | Servidor fora do ar (urgente) | EMP009 | O sistema principal caiu para todo o time e estamos sem conseguir operar agora. | it | high | high | critical |
| 08 | Nova conta de acesso | EMP001 | Entrei em um novo projeto e preciso acesso ao repositório compartilhado da equipe. | it | low | medium | low |
| 09 | Impressora com defeito | EMP005 | A impressora do andar está travando papel e ninguém consegue imprimir documentos. | facilities | low | medium | low |
| 10 | Solicitação de férias | EMP014 | Quero entender como registrar minhas férias do próximo mês no portal interno. | hr | low | low | low |
| 11 | Falta de papel | EMP019 | Acabou o papel na impressora do setor e precisamos imprimir poucas folhas hoje. | facilities | low | low | low |
| 12 | Problema com VPN | EMP001 | A VPN parou de autenticar e eu tenho reunião com cliente em 20 minutos. | it | medium | high | high |
| 13 | Software não instala | EMP020 | Não consigo instalar a ferramenta necessária para a aula e já tentei reiniciar a máquina. | it | medium | medium | medium |
| 14 | Relatório financeiro | EMP013 | O relatório de fechamento financeiro está inconsistente e preciso validar os números até o fim do dia. | finance | high | medium | high |
| 15 | Treinamento de segurança | EMP011 | Quero saber como participar do treinamento obrigatório de segurança da informação. | hr | low | low | low |
| 16 | Mudança de escritório | EMP007 | Minha equipe vai mudar de sala e precisamos de apoio para mesas, cadeiras e pontos físicos. | facilities | medium | low | low |
| 17 | Problema com badge | EMP016 | Meu badge parou de funcionar e não consigo entrar na área restrita do andar. | security | medium | medium | high |
| 18 | Solicitação de notebook novo | EMP017 | Meu notebook atual está muito lento para o trabalho e gostaria de solicitar substituição. | it | medium | low | low |
| 19 | Alarme de segurança | EMP006 | O alarme disparou na sala de equipamentos e há suspeita de acesso indevido. | security | high | high | critical |
| 20 | Dúvida sobre benefícios | EMP004 | Tenho dúvida sobre o plano de benefícios e não sei onde consultar essa informação. | hr | low | low | low |

## Casos adicionais úteis para discussão em aula

### Ambíguos

- cenário 06: mistura processo interno e possível problema de sistema
- cenário 08: pode ser tratado como acesso técnico ou solicitação operacional

### Urgentes

- cenário 07: indisponibilidade ampla
- cenário 12: bloqueio com impacto imediato
- cenário 19: incidente de segurança

### Baixo impacto

- cenário 04
- cenário 10
- cenário 11
- cenário 20

### Alto impacto

- cenário 07
- cenário 14
- cenário 19

## Sugestão de exercício

1. enviar cada mensagem para um webhook do n8n ou Make
2. usar LLM para classificar categoria, impact e urgency
3. comparar com o resultado pedagógico esperado
4. chamar `/api/v1/priority/check`
5. abrir ticket apenas quando os campos estiverem válidos
