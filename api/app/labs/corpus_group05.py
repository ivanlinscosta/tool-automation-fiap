INTENT_MESSAGES = {
    "troca_produto": (
        "Recebi o tenis no tamanho errado e preciso solicitar a troca ainda esta semana.",
        "O produto veio diferente da foto e quero entender como funciona a troca.",
        "Comprei um liquidificador e preciso trocar por outro modelo com mais potencia.",
        "Meu pedido chegou, mas quero substituir o item por outra cor disponivel no site.",
    ),
    "defeito_produto": (
        "A cafeteira parou de funcionar no segundo uso e preciso de suporte urgente.",
        "O fone chegou sem carregar e parece ter defeito de fabrica.",
        "Abri a caixa e o produto veio quebrado. Como aciono a garantia?",
        "O notebook aquece demais e desliga sozinho desde o primeiro dia.",
    ),
    "rastreio_pedido": (
        "Meu pedido ainda nao atualizou no rastreio. Conseguem verificar?",
        "Preciso saber onde esta a entrega porque o prazo informado ja passou.",
        "O codigo de rastreio nao mostra movimentacao desde anteontem.",
        "A transportadora informou rota, mas o pedido ainda nao chegou aqui.",
    ),
    "fatura_segunda_via": (
        "Preciso da segunda via da fatura para concluir o pagamento hoje.",
        "Nao localizei o boleto do pedido. Podem reenviar a cobranca?",
        "Meu financeiro pediu a fatura atualizada da compra feita no portal.",
        "Conseguem enviar outra via da nota e do boleto do meu pedido?",
    ),
    "reclamacao_atraso": (
        "A entrega atrasou muito e preciso de uma resposta concreta hoje.",
        "Comprei para presentear e o pedido nao chegou no prazo prometido.",
        "Ja falei com a transportadora, mas ninguem explica o atraso na entrega.",
        "Estou insatisfeito porque a compra esta vencida e sem previsao de chegada.",
    ),
    "duvida_uso": (
        "Gostaria de orientacao para configurar o produto corretamente na primeira instalacao.",
        "Tenho duvidas sobre como ativar a garantia estendida no aplicativo.",
        "Podem me explicar como usar a funcao principal do equipamento?",
        "Nao entendi o manual e preciso de ajuda para utilizar o item com seguranca.",
    ),
}


def build_message(rng, intencao: str) -> str:
    return rng.choice(INTENT_MESSAGES[intencao])
