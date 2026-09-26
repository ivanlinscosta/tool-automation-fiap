LEAD_MESSAGES_HIGH_INTENT = (
    "Precisamos de um orcamento para 40 licencas do Quantum Analytics ate o fim do mes, podemos pagar a vista.",
    "Estamos avaliando tres fornecedores para o projeto de infraestrutura. Quero comparar preco e prazo de entrega.",
    "Tenho orcamento aprovado e preciso contratar ainda esta semana. Alguem pode me atender hoje?",
    "Gerente de TI de uma empresa de 800 colaboradores, precisamos renovar 250 licencas. Quero agendar uma reuniao com o comercial.",
    "Recebi a proposta semana passada e quero avancar. Podem enviar a ordem de compra e o contato do responsavel?",
    "Somos 12 unidades e queremos contratar o pacote enterprise. Qual o melhor preco para 600 usuarios?",
    "Minha empresa precisa de faturamento para emitir nota. Podem enviar a proposta comercial completa hoje?",
    "Quero contratar 3 planos do Quantum Analytics pelo menor valor possivel. Podem confirmar a disponibilidade?",
    "O valor cabe no orcamento que liberamos. So precisamos de uma proposta formal para o nosso comite de compras.",
    "Comprei no site e gostei. Quero contratar mais 20 usuarios ainda neste mes. Como faco?",
)

LEAD_MESSAGES_NURTURING = (
    "Vi o anuncio no linkedin e quero receber mais materiais sobre solucoes de dados para o setor de saude.",
    "Estamos em fase de estudos e voltamos a falar no proximo trimestre. Podem me adicionar na newsletter?",
    "Nao tenho orcamento agora, mas estamos avaliando internamente. Me chamem em seis meses, por favor.",
    "Gostaria de entender melhor como funciona a integracao antes de qualquer proposta comercial.",
    "Pode me enviar um material tecnico e um caso de uso do mesmo segmento do meu?",
    "Obrigado. Quero apenas receber conteudo educativo por enquanto, sem compromisso comercial.",
    "Estamos fazendo um estudo interno de mercado e o material ajuda bastante. Sem pressa para fechar nada.",
    "Apenas curiosidade por enquanto. Sem pressa e sem proposta, so quero acompanhar as novidades.",
)

LEAD_MESSAGES_HIGH_VALUE = (
    "Sou diretor de tecnologia e vou decidir o fornecedor do grupo inteiro. Preciso de proposta para 2000 usuarios.",
    "Temos aporte aprovado para modernizar a area de dados. O investimento previsto passa de 1 milhao de reais.",
    "Minha organizacao tem contrato de licenca anual e quero uma proposta para ampliar para 5 mil usuarios.",
    "Sou comprador corporativo e preciso de condicoes especiais para volume acima de mil licencas.",
)

LEAD_MESSAGES_TECHNICAL = (
    "Duvido que a solucao atenda a nossa arquitetura de dados legada sem um projeto de migracao.",
    "Minha duvida e sobre a integracao via API e o SLA de disponibilidade. Precisamos de 99.9 por cento.",
    "Funciona com o nosso banco de dados legado? Precisamos de prova de conceito antes de avancar.",
    "Temos uma exigencia de residencia de dados no pais que pode ser um bloqueio na avaliacao.",
    "Qual a latencia esperada da API e existe plano de recuperacao de desastre documentado?",
    "Seguranca da informacao vai exigir uma avaliacao do time de voces antes de aprovarmos qualquer coisa.",
)

LEAD_MESSAGES_COMPLAINT = (
    "Reclamei do atendimento anterior e nao resolveu. Ja sou cliente e nao quero passar por isso de novo.",
    "Recebi tres propostas com valores diferentes para o mesmo produto. Isso e aceitavel?",
    "Meu desconto prometido no chat nao foi aplicado no contrato. Quero resolver isso antes de fechar.",
)

LEAD_MESSAGES_UNINTERESTED = (
    "Nao temos interesse, por favor parem de enviar mensagens. Nao autorizo contato comercial.",
    "Nao sou eu quem decide essa contratacao. Por favor, nao insistam comigo.",
    "Ja contratamos outro fornecedor este ano. Nao precisamos de novas propostas.",
    "Nao possuo orcamento e nao pretendo ter nos proximos 12 meses. Pode descadastrar meu contato?",
)

LEAD_MESSAGES_ANONYMOUS = (
    "Boa tarde, gostariamos de saber mais sobre o produto. Podem me passar o contato?",
    "ola, vi o material de voces e quero mais informacao.",
    "Interessei no anuncio publicado, me chamem.",
    "Qual o proximo passo para contratar?",
    "Bom dia, tudo bem? Estou analisando opcoes e gostaria de trocar um e-mail com alguem do time comercial.",
    "mensagem sem assinatura",
    "   ",
)

LEAD_MESSAGES_LOW_CONFIDENCE = (
    "Bom dia. Sobre aquele assunto que falamos na outra semana, precisaríamos retomar a conversa.",
    "Sao as coisas do projeto. Aquela pessoa que te falei ja respondeu?",
    "A gente precisa ver isso, mas o nivel do pessoal de ti ainda nao esta definido.",
    "Talvez seja melhor falar depois, minha agenda essa semana esta lotada e nao sei se consigo levar adiante.",
    "Sobre a proposta: ela existe, mas talvez tenhamos de refazer tudo por causa de mudanca de escopo.",
    "Acho que da para chamar o pessoal, mas nao sei quem resolve a parte contratual. Voces conseguem falar direto com ele?",
)

LEAD_QUALITY_POOLS = (
    "lead_high_intent",
    "lead_nurturing",
    "lead_high_value",
    "lead_technical",
    "lead_complaint",
    "lead_uninterested",
    "lead_anonymous",
    "lead_low_confidence",
)

LEAD_CATEGORY_BY_POOL = {
    "lead_high_intent": ("venda_imediata", True),
    "lead_nurturing": ("nurturing", True),
    "lead_high_value": ("alto_valor", True),
    "lead_technical": ("pesquisa_tecnica", True),
    "lead_complaint": ("reclamacao_comercial", True),
    "lead_uninterested": ("sem_interesse", False),
    "lead_anonymous": ("sem_identificacao", False),
    "lead_low_confidence": ("nurturing", True),
}

LEAD_MESSAGES_BY_POOL = {
    "lead_high_intent": LEAD_MESSAGES_HIGH_INTENT,
    "lead_nurturing": LEAD_MESSAGES_NURTURING,
    "lead_high_value": LEAD_MESSAGES_HIGH_VALUE,
    "lead_technical": LEAD_MESSAGES_TECHNICAL,
    "lead_complaint": LEAD_MESSAGES_COMPLAINT,
    "lead_uninterested": LEAD_MESSAGES_UNINTERESTED,
    "lead_anonymous": LEAD_MESSAGES_ANONYMOUS,
    "lead_low_confidence": LEAD_MESSAGES_LOW_CONFIDENCE,
}


def build_lead_message(rng, quality: str) -> str:
    return rng.choice(LEAD_MESSAGES_BY_POOL[quality])
