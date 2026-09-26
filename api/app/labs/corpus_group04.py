GROUP04_MESSAGES_BY_INTENT = {
    "cancelamento": (
        "Quero cancelar minha assinatura antes da renovacao de hoje.",
        (
            "Preciso encerrar o servico porque a cobranca nao faz mais sentido "
            "para minha area."
        ),
        "Nao quero continuar com o plano atual e preciso do cancelamento agora.",
    ),
    "troca": (
        "Recebi o item errado e preciso trocar pelo modelo correto.",
        "Gostaria de substituir o produto por outra versao do mesmo pacote.",
        "Quero trocar a compra porque o tamanho nao serviu na operacao.",
    ),
    "duvida_produto": (
        "Tenho duvida sobre a integracao e os recursos disponiveis no plano.",
        "Preciso entender se o produto atende a minha necessidade tecnica.",
        "Qual a diferenca entre as opcoes do catalogo para esse servico?",
    ),
    "reclamacao": (
        "O atendimento anterior nao resolveu e continuo com o mesmo problema.",
        "Estou reclamando porque o processo ficou mais lento do que o combinado.",
        "A experiencia foi ruim e preciso de uma resposta imediata.",
    ),
    "elogio": (
        "Quero registrar um elogio pelo suporte rapido e atencioso.",
        "O time resolveu tudo muito bem e gostaria de agradecer.",
        "Atendimento excelente; parabens pela agilidade do canal.",
    ),
    "reclamacao_financ": (
        "A fatura veio com valor incorreto e preciso revisar a cobranca.",
        "Tenho uma reclamacao financeira sobre desconto nao aplicado.",
        "Foi cobrado um valor indevido no meu contrato deste mes.",
    ),
    "upgrade": (
        "Quero fazer upgrade para um plano maior ainda esta semana.",
        "Precisamos ampliar o pacote contratado e entender os proximos passos.",
        "Gostaria de aumentar o numero de usuarios com urgencia.",
    ),
}


def build_customer_message(rng, intent: str) -> str:
    return rng.choice(GROUP04_MESSAGES_BY_INTENT[intent])
