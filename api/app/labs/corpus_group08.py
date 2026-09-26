UNLOCK_REASONS = (
    "Cliente informou que efetuara o pagamento e solicita restabelecimento do servico.",
    "Assinante pediu desbloqueio temporario ate a compensacao do boleto em aberto.",
    "Empresa sinalizou promessa de pagamento e requer reativacao do contrato hoje.",
    "Consumidor deseja liberar o acesso para manter a operacao enquanto regulariza a fatura.",
)


def build_unlock_reason(rng) -> str:
    return rng.choice(UNLOCK_REASONS)
