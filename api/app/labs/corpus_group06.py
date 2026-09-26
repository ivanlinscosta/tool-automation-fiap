EMAIL_BODIES = (
    "Solicito abertura de compra. CAPEX {capex}. Fornecedor: {supplier}. Itens: {items}. Valor total: R$ {total}. Prazo desejado: {days} dias.",
    "Bom dia, precisamos seguir com a requisicao CAPEX {capex}. Supplier {supplier}. Descricao: {items}. Montante estimado de R$ {total}.",
    "Favor processar a demanda de compra referente ao CAPEX {capex}. Fornecedor aprovado: {supplier}. Lista de itens: {items}. Total previsto R$ {total}.",
    "Encaminho pedido para emissao de PO. CAPEX {capex}; fornecedor {supplier}; itens {items}; valor consolidado R$ {total}; entrega em {days} dias.",
)


def build_email_body(rng, *, capex: str, supplier: str, items: str, total: str, days: int) -> str:
    template = rng.choice(EMAIL_BODIES)
    return template.format(capex=capex, supplier=supplier, items=items, total=total, days=days)
