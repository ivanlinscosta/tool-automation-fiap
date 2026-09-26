COLLECTION_TEMPLATES = {
    "ENVIAR_EMAIL": (
        "Prezado cliente, identificamos o titulo {titulo} em aberto no valor de R$ {valor}. Favor regularizar.",
        "Lembramos que o recebivel {titulo} venceu e segue pendente. Valor atualizado: R$ {valor}.",
    ),
    "ENVIAR_SMS": (
        "Titulo {titulo} vencido. Regularize o valor de R$ {valor} para evitar novas acoes.",
        "Cobranca automatica: recebivel {titulo} pendente no valor de R$ {valor}.",
    ),
    "LIGAR": (
        "Contato telefonico necessario para o titulo {titulo} com atraso relevante.",
        "Acionar equipe de voz para negociar o recebivel {titulo} no valor de R$ {valor}.",
    ),
    "SUSPENDER": (
        "Conta elegivel para suspensao por inadimplencia associada ao titulo {titulo}.",
        "Aplicar restricao operacional vinculada ao titulo {titulo} devido ao atraso prolongado.",
    ),
}


def build_collection_message(rng, acao: str, titulo: str, valor: float) -> str:
    return rng.choice(COLLECTION_TEMPLATES[acao]).format(titulo=titulo, valor=f"{valor:.2f}")
