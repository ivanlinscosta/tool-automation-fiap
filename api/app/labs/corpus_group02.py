GROUP02_VALID_NOTES = (
    "Taxa importada com CNPJ validado e indexador mapeado.",
    "Registro conciliado com planilha mensal do mercado primario.",
    "Linha aprovada na ingestao automatica sem divergencias.",
    "Documento consolidado com vencimento dentro da janela esperada.",
)

GROUP02_INVALID_CNPJ_NOTES = (
    "Linha rejeitada por CNPJ com digitos verificadores invalidos.",
    "CNPJ inconsistente com o padrao cadastral do emissor.",
    "Falha de validacao: CNPJ invalido na carga do mes.",
)

GROUP02_EXPIRED_NOTES = (
    "Titulo com vencimento expirado antes da data de referencia do laboratorio.",
    "Vencimento expirado; revisar se a emissao deveria permanecer ativa.",
    "Linha com papel vencido e mantida para exercicio de saneamento.",
)

GROUP02_UNMAPPED_NOTES = (
    "Indexador nao mapeado para codigo interno do mercado primario.",
    "Carga rejeitada por indexador nao cadastrado na tabela de mapeamento.",
    "Indexador nao mapeado; revisar dicionario operacional antes do reprocessamento.",
)
