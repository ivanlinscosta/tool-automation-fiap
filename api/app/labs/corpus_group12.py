FRAMEWORKS = ("xgboost", "sklearn", "lightgbm", "pytorch")

MODEL_SUMMARIES = (
    "Modelo para apoio a decisao com monitoramento operacional continuo.",
    "Classificador supervisionado usado em fluxo de priorizacao interna.",
    "Modelo tabular para triagem inicial com explicabilidade agregada.",
)

MODEL_LIMITATIONS = (
    "Nao deve ser usado como criterio unico de aprovacao.",
    "Sensivel a drift em bases fora do perfil historico.",
    "Requer monitoramento semanal de estabilidade e vies.",
)
