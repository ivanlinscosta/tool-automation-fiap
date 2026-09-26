import random
import unicodedata
from datetime import date, datetime, time, timedelta

from ..config import settings


LAB_SEED = settings.LABS_SEED
LAB_TODAY = date.fromisoformat(settings.LABS_TODAY)
LAB_MIN_RECORDS = settings.LABS_MIN_RECORDS
LAB_NOW = datetime.combine(LAB_TODAY, time(23, 59, 59))
LAB_ORIGIN_EPOCH = datetime.combine(LAB_TODAY, time(0, 0, 0))

FIRST_NAMES = (
    "Ana", "Bruno", "Carla", "Diego", "Elisa", "Felipe", "Gabriela", "Henrique", "Isabela", "Joao",
    "Karina", "Lucas", "Mariana", "Nicolas", "Olivia", "Pedro", "Rafaella", "Sergio", "Tatiane", "Ugo",
    "Vitoria", "William", "Yasmin", "Andre", "Bruna", "Caio", "Daniela", "Erica", "Fabio", "Gustavo",
    "Helena", "Igor", "Julia", "Katia", "Leonardo", "Manuela", "Nathan", "Otavio", "Patricia", "Rafael",
    "Sabrina", "Thiago", "Vanessa", "Wagner", "Zilda", "Andreia", "Cecilia", "Douglas", "Eliane",
)

LAST_NAMES = (
    "Oliveira", "Silva", "Santos", "Souza", "Costa", "Pereira", "Almeida", "Nascimento", "Lima", "Araujo",
    "Fernandes", "Carvalho", "Ribeiro", "Martins", "Rocha", "Barbosa", "Cardoso", "Teixeira", "Moreira", "Gomes",
    "Melo", "Freitas", "Pinto", "Moura", "Correia", "Dias", "Farias", "Neves", "Monteiro", "Cavalcanti",
    "Ramos", "Campos", "Vieira", "Salles", "Fontes", "Coelho", "Borges", "Azevedo", "Tavares", "Macedo",
    "Andrade", "Duarte", "Bezerra", "Teles", "Guimaraes", "Xavier", "Moraes", "Peixoto", "Fonseca",
)

COMPANY_PREFIX = (
    "Alfa", "Boreal", "Cedro", "Delta", "Estrela", "Ferrovia", "Granito", "Horizonte", "Ita", "Jaguar",
    "Kaete", "Lumen", "Maritima", "Norte", "Orion", "Paranaiba", "Quartzo", "Rubi", "Serrana", "Trilha",
    "Ubatã", "Verde", "Willow", "Xingu", "Ypê", "Zafira", "Andorinha", "Bandeirante", "Cristal", "Dunas",
)

COMPANY_SUFFIX = (
    "Tecnologia", "Logistica", "Energia", "Saude", "Financeira", "Varejo", "Agro", "Construcoes",
    "Servicos", "Industria", "Alimentos", "Transporte", "Consultoria", "Telecom", "Seguros",
)

EMAIL_DOMAINS = (
    "example.com", "example.com.br", "example.net", "example.org", "contato-example.com.br",
)

CITIES = (
    "Sao Paulo", "Rio de Janeiro", "Belo Horizonte", "Porto Alegre", "Salvador", "Curitiba",
    "Recife", "Fortaleza", "Brasilia", "Campinas", "Manaus", "Goiania", "Natal", "Vitoria",
)

STATES = ("SP", "RJ", "MG", "RS", "BA", "PR", "PE", "CE", "DF", "SP", "PR", "PE", "RN", "ES")

SEGMENTS = (
    "enterprise", "mid_market", "small_business", "startup", "public_sector", "nonprofit",
)

CHANNELS = ("whatsapp", "email", "chat", "phone", "instagram", "web_form")

EMAIL_LOCALPARTS = ("contato", "financeiro", "comercial", "suporte", "nucleo", "ti", "rh", "fiscal")


def group_rng(group_id: int) -> random.Random:
    return random.Random(LAB_SEED * 100 + group_id)


def sub_rng(parent: random.Random, salt: int) -> random.Random:
    return random.Random(f"{parent.getstate()[1][0]}:{salt}")


def weighted(rng: random.Random, options: list[tuple[str, int]]) -> str:
    population = [option for option, _ in options]
    weights = [weight for _, weight in options]
    return rng.choices(population, weights=weights, k=1)[0]


def person_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def company_name(rng: random.Random) -> str:
    return f"{rng.choice(COMPANY_PREFIX)} {rng.choice(COMPANY_SUFFIX)}"


def email_address(rng: random.Random, name: str | None = None, domain: str | None = None) -> str:
    if name is None:
        name = person_name(rng)
    normalized = _slug(name)
    suffix = "" if rng.random() < 0.6 else str(rng.randint(1, 99))
    return f"{normalized}{suffix}@{domain or rng.choice(EMAIL_DOMAINS)}"


def _slug(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(char for char in decomposed if not unicodedata.combining(char))
    return ascii_only.lower().replace(" ", ".").replace("'", "")


def _check_digit(base: list[int], weights: list[int]) -> int:
    total = sum(digit * weight for digit, weight in zip(base, weights, strict=True))
    remainder = (total * 10) % 11
    return 0 if remainder == 10 else remainder


def cpf(rng: random.Random, valid: bool = True) -> str:
    base = [rng.randint(0, 9) for _ in range(9)]
    first = _check_digit(base, [10, 9, 8, 7, 6, 5, 4, 3, 2])
    second = _check_digit([*base, first], [11, 10, 9, 8, 7, 6, 5, 4, 3, 2])
    digits = [*base, first, second]
    if not valid:
        digits[-1] = (digits[-1] + 1) % 10
    formatted = "".join(str(digit) for digit in digits)
    return f"{formatted[:3]}.{formatted[3:6]}.{formatted[6:9]}-{formatted[9:]}"


def cnpj(rng: random.Random, valid: bool = True) -> str:
    base = [rng.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    first = _check_digit(base, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second = _check_digit([*base, first], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    digits = [*base, first, second]
    if not valid:
        digits[-1] = (digits[-1] + 1) % 10
    formatted = "".join(str(digit) for digit in digits)
    return f"{formatted[:2]}.{formatted[2:5]}.{formatted[5:8]}/{formatted[8:12]}-{formatted[12:]}"


def is_valid_cpf(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    first = _check_digit(digits[:9], [10, 9, 8, 7, 6, 5, 4, 3, 2])
    second = _check_digit(digits[:10], [11, 10, 9, 8, 7, 6, 5, 4, 3, 2])
    return first == digits[9] and second == digits[10]


def is_valid_cnpj(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    first = _check_digit(digits[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second = _check_digit(digits[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return first == digits[12] and second == digits[13]


def brazilian_phone(rng: random.Random) -> str:
    ddd = rng.choice(("11", "21", "31", "41", "48", "51", "61", "71", "81", "85"))
    prefix = "9" if rng.random() < 0.75 else "8"
    number = rng.randint(1000000, 9999999)
    return f"({ddd}) {prefix}{number}"


def postal_code(rng: random.Random) -> str:
    return f"{rng.randint(10000, 99999)}-{rng.randint(100, 999)}"


def money(rng: random.Random, low: float, high: float, decimals: int = 2) -> float:
    return round(rng.uniform(low, high), decimals)


def percentage(rng: random.Random, low: float, high: float) -> float:
    return round(rng.uniform(low, high), 4)


def iso_timestamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def moment(
    rng: random.Random,
    *,
    start_days_ago: int = 365,
    end_days_ago: int = 0,
    earliest_hour: int = 0,
    latest_hour: int = 23,
) -> datetime:
    low, high = sorted((end_days_ago, start_days_ago))
    return datetime(LAB_TODAY.year, LAB_TODAY.month, LAB_TODAY.day) - timedelta(
        days=rng.randint(low, high),
        hours=rng.randint(earliest_hour, latest_hour),
        minutes=rng.randint(0, 59),
        seconds=rng.randint(0, 59),
    )


def moment_after(
    rng: random.Random,
    origin: datetime,
    *,
    min_minutes: int = 5,
    max_days: int = 5,
) -> datetime:
    span = max(min_minutes + 1, max_days * 24 * 60)
    return origin + timedelta(minutes=rng.randint(min_minutes, span))


def moment_before(rng: random.Random, origin: datetime, *, min_minutes: int = 5, max_days: int = 5) -> datetime:
    span = max(min_minutes + 1, max_days * 24 * 60)
    return origin - timedelta(minutes=rng.randint(min_minutes, span))


def clamp_to_lab_now(value: datetime) -> datetime:
    return min(value, LAB_NOW)


def next_moment(
    rng: random.Random,
    origin: datetime,
    *,
    min_minutes: int = 5,
    max_days: int = 5,
) -> datetime:
    low = origin + timedelta(minutes=min_minutes)
    if LAB_NOW <= low:
        return LAB_NOW
    span = int((LAB_NOW - low).total_seconds() // 60)
    return low + timedelta(minutes=rng.randint(0, span))


def previous_moment(
    rng: random.Random,
    origin: datetime,
    *,
    min_minutes: int = 5,
    max_days: int = 400,
) -> datetime:
    high = origin - timedelta(minutes=min_minutes)
    floor = LAB_ORIGIN_EPOCH - timedelta(days=max_days)
    if high <= floor:
        return floor
    span = int((high - floor).total_seconds() // 60)
    return high - timedelta(minutes=rng.randint(0, span))


def date_before(rng: random.Random, origin: date, *, min_days: int = 1, max_days: int = 400) -> date:
    return origin - timedelta(days=rng.randint(min_days, max_days))


def date_after(rng: random.Random, origin: date, *, min_days: int = 1, max_days: int = 60) -> date:
    return origin + timedelta(days=rng.randint(min_days, max_days))


def shuffled_cycle(rng: random.Random, total: int, buckets: list[str]) -> list[str]:
    pool = [buckets[index % len(buckets)] for index in range(total)]
    rng.shuffle(pool)
    return pool
