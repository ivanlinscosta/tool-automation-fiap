GROUP03_LINE_TEMPLATES = (
    "{empresa} | {cnpj} | {produto} | {valor} | {contato} | {email} | {stage}",
)

GROUP03_VALIDATION_OK = (
    "Linha pronta para sincronizacao no CRM.",
    "Dados obrigatorios validados e produto mapeado para o pipeline.",
    "Registro elegivel para criacao de contato e deal no Bitrix24.",
)

GROUP03_VALIDATION_CNPJ = (
    "CNPJ invalido; revisar a linha antes da carga no CRM.",
    "Documento da empresa falhou na validacao de digitos verificadores.",
)

GROUP03_VALIDATION_VALUE = (
    "Valor da oportunidade nao pode ser zero ou negativo.",
    "Montante informado fora da faixa aceita para o pipeline comercial.",
)

GROUP03_VALIDATION_PRODUCT = (
    "Produto sem mapeamento para pipeline no Bitrix24.",
    "Carga parcial: produto nao encontrado na tabela de mapeamento.",
)

GROUP03_LOAD_LOG_INFO = (
    "Carga recebida para processamento automatizado.",
    "Lista convertida em oportunidades e sincronizada com o CRM.",
)

GROUP03_LOAD_LOG_WARN = (
    "Carga processada com linhas invalidas ou produtos sem mapeamento.",
    "Sincronizacao parcial: alguns deals nao foram criados.",
)

GROUP03_LOAD_LOG_ERROR = (
    "Solicitante nao autorizado para executar cargas no Bitrix24.",
    "Reprocessamento bloqueado por conflito de idempotencia.",
)
