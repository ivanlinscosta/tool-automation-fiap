import json
import logging
import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from .database import SessionLocal
from ..models.approval import Approval
from ..models.customer import Customer
from ..models.event import Event
from ..models.interaction import Interaction
from ..models.inventory import InventoryItem
from ..models.order import Order, OrderItem
from ..models.policy import Policy
from ..models.product import Product
from ..models.promotion import Promotion
from ..models.refund import Refund
from ..models.return_record import ReturnRecord
from ..models.shipment import Shipment
from ..models.support_case import SupportCase


logger = logging.getLogger(__name__)

QUANTUM_SEED = 42
TODAY = date(2026, 9, 13)

RETURN_WINDOW_BY_COUNTRY = {
    "BR": 30, "MX": 30, "AR": 10, "CO": 15, "CL": 30, "PT": 14, "US": 30,
}

SCENARIOS = {
    "cenario_01_pedido_em_transito": {"customer": "CUS-1001", "order": "ORD-2026-10001"},
    "cenario_02_pedido_atrasado": {"customer": "CUS-1007", "order": "ORD-2026-10023"},
    "cenario_03_pedido_perdido": {"customer": "CUS-1005", "order": "ORD-2026-10024"},
    "cenario_04_premium_com_problema": {"customer": "CUS-1001", "order": "ORD-2026-10014"},
    "cenario_05_produto_sem_estoque": {"sku": "QTM-NBK-00150"},
    "cenario_06_produto_estoque_baixo": {"sku": "QTM-ACC-00100"},
    "cenario_07_devolucao_dentro_prazo": {"customer": "CUS-1001", "order": "ORD-2026-10005", "return": "RET-90001"},
    "cenario_08_devolucao_fora_prazo": {"customer": "CUS-1001", "order": "ORD-2026-10007", "return": "RET-90002"},
    "cenario_09_refund_pequeno": {"order": "ORD-2026-10012", "refund": "REF-10005"},
    "cenario_10_refund_alto": {"order": "ORD-2026-10001", "approval": "APR-1002"},
    "cenario_11_support_case_aberto": {"customer": "CUS-1010", "case": "CASE-2026-1002"},
    "cenario_12_produto_promocao": {"sku": "QTM-NBK-00123", "promotion": "PROMO-100"},
    "cenario_13_pedido_entregue": {"customer": "CUS-1002", "order": "ORD-2026-10010"},
    "cenario_14_pedido_cancelado": {"customer": "CUS-1003", "order": "ORD-2026-10025"},
    "cenario_15_falha_transportadora": {"customer": "CUS-1011", "order": "ORD-2026-10030"},
}

FIRST_NAMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elisa", "Felipe", "Gabriela", "Henrique", "Isabela", "João",
    "Karina", "Lucas", "Mariana", "Nícolas", "Olívia", "Pedro", "Rafaella", "Sérgio", "Tatiane", "Ugo",
    "Vitória", "William", "Yasmin", "André", "Bruna", "Caio", "Daniela", "Érica", "Fábio", "Gustavo",
    "Helena", "Igor", "Júlia", "Kátia", "Leonardo", "Manuela", "Nathan", "Otávio", "Patrícia", "Rafael",
]

LAST_NAMES = [
    "Oliveira", "Silva", "Santos", "Souza", "Costa", "Pereira", "Almeida", "Nascimento", "Lima", "Araújo",
    "Fernandes", "Carvalho", "Ribeiro", "Martins", "Rocha", "Barbosa", "Cardoso", "Teixeira", "Moreira", "Gomes",
    "Melo", "Freitas", "Pinto", "Moura", "Correia", "Dias", "Farias", "Neves", "Monteiro",
    "Cavalcanti", "Ramos", "Campos", "Vieira", "Salles", "Fontes", "Coelho", "Borges", "Azevedo", "Tavares",
]

COUNTRY_CITIES = {
    "BR": ["São Paulo", "Rio de Janeiro", "Belo Horizonte", "Porto Alegre", "Salvador", "Curitiba"],
    "MX": ["Cidade do México", "Guadalajara", "Monterrey"],
    "AR": ["Buenos Aires", "Córdoba"],
    "CO": ["Bogotá", "Medellín"],
    "CL": ["Santiago", "Valparaíso"],
    "PT": ["Lisboa", "Porto"],
    "US": ["Miami", "New York"],
}

WAREHOUSES = [
    {"warehouse_id": "BR-SP-01", "city": "São Paulo", "country": "BR"},
    {"warehouse_id": "BR-RJ-01", "city": "Rio de Janeiro", "country": "BR"},
    {"warehouse_id": "BR-MG-01", "city": "Belo Horizonte", "country": "BR"},
    {"warehouse_id": "BR-RS-01", "city": "Porto Alegre", "country": "BR"},
    {"warehouse_id": "BR-BA-01", "city": "Salvador", "country": "BR"},
    {"warehouse_id": "MX-MEX-01", "city": "Cidade do México", "country": "MX"},
    {"warehouse_id": "AR-BUE-01", "city": "Buenos Aires", "country": "AR"},
    {"warehouse_id": "CO-BOG-01", "city": "Bogotá", "country": "CO"},
    {"warehouse_id": "CL-SCL-01", "city": "Santiago", "country": "CL"},
    {"warehouse_id": "PT-LIS-01", "city": "Lisboa", "country": "PT"},
]

PINNED_CUSTOMERS = {
    "CUS-1001": {"name": "Marina Oliveira", "email": "marina.oliveira@example.com", "country": "BR", "city": "São Paulo", "segment": "premium", "loyalty_tier": "gold", "customer_since": date(2021, 3, 12), "lifetime_value": 18450.90, "preferred_channel": "whatsapp", "total_orders": 47},
    "CUS-1002": {"name": "Bianca Campos", "email": "bianca.campos@example.com", "country": "BR", "city": "Curitiba", "segment": "standard", "loyalty_tier": "silver", "customer_since": date(2026, 8, 2), "lifetime_value": 3200.00, "preferred_channel": "chat", "total_orders": 3},
    "CUS-1003": {"name": "Rafael Almeida", "email": "rafael.almeida@example.com", "country": "BR", "city": "São Paulo", "segment": "standard", "loyalty_tier": "silver", "customer_since": date(2020, 5, 20), "lifetime_value": 9800.50, "preferred_channel": "email", "total_orders": 28},
    "CUS-1004": {"name": "Camila Duarte", "email": "camila.duarte@example.com", "country": "BR", "city": "Rio de Janeiro", "segment": "standard", "loyalty_tier": "bronze", "customer_since": date(2022, 1, 15), "lifetime_value": 5400.00, "preferred_channel": "email", "total_orders": 22},
    "CUS-1005": {"name": "Gustavo Freitas", "email": "gustavo.freitas@example.com", "country": "BR", "city": "Porto Alegre", "segment": "premium", "loyalty_tier": "gold", "customer_since": date(2023, 6, 1), "lifetime_value": 12300.75, "preferred_channel": "whatsapp", "total_orders": 15},
    "CUS-1006": {"name": "Helena Martins", "email": "helena.martins@example.com", "country": "BR", "city": "São Paulo", "segment": "premium", "loyalty_tier": "platinum", "customer_since": date(2019, 11, 30), "lifetime_value": 48200.90, "preferred_channel": "phone", "total_orders": 63},
    "CUS-1007": {"name": "Igor Santana", "email": "igor.santana@example.com", "country": "BR", "city": "Belo Horizonte", "segment": "standard", "loyalty_tier": "silver", "customer_since": date(2022, 9, 10), "lifetime_value": 7100.20, "preferred_channel": "chat", "total_orders": 12},
    "CUS-1008": {"name": "Júlia Nogueira", "email": "julia.nogueira@example.com", "country": "BR", "city": "Salvador", "segment": "budget", "loyalty_tier": "none", "customer_since": date(2024, 3, 5), "lifetime_value": 980.00, "preferred_channel": "web", "total_orders": 4},
    "CUS-1009": {"name": "Ximena Rojas", "email": "ximena.rojas@example.com", "country": "MX", "city": "Cidade do México", "segment": "premium", "loyalty_tier": "gold", "customer_since": date(2023, 8, 22), "lifetime_value": 15600.00, "preferred_channel": "whatsapp", "total_orders": 11},
    "CUS-1010": {"name": "Otávio Prado", "email": "otavio.prado@example.com", "country": "BR", "city": "São Paulo", "segment": "premium", "loyalty_tier": "gold", "customer_since": date(2021, 7, 18), "lifetime_value": 22100.40, "preferred_channel": "chat", "total_orders": 34},
    "CUS-1011": {"name": "Natália Rocha", "email": "natalia.rocha@example.com", "country": "BR", "city": "Rio de Janeiro", "segment": "standard", "loyalty_tier": "silver", "customer_since": date(2022, 5, 14), "lifetime_value": 6900.00, "preferred_channel": "whatsapp", "total_orders": 9},
}

PRODUCT_LINES = [
    ("NBK", "electronics", "notebooks", "QuantumTech", (2999.90, 7999.90), ["QuantumBook Pro 16", "QuantumBook Air 15", "QuantumBook Go 14", "QuantumBook Studio 16"]),
    ("PHN", "electronics", "smartphones", "QuantumTech", (1299.90, 5499.90), ["QuantumPhone 13", "QuantumPhone 14", "QuantumPhone 15", "QuantumPhone Lite 12", "QuantumPhone Max 15", "QuantumPhone Mini 13"]),
    ("TAB", "electronics", "tablets", "QuantumTech", (899.90, 3499.90), ["QuantumTab 10", "QuantumTab 11 Pro", "QuantumTab Lite 9", "QuantumTab Studio 12"]),
    ("ACC", "electronics", "accessories", "QuantumTech", (49.90, 799.90), ["Teclado Quantum Key", "Headset Quantum Sound", "Webcam Quantum Cam", "Hub Quantum Link", "Pen Drive Quantum 128GB", "Power Bank Quantum 20K", "SSD Quantum 1TB", "Teclado Quantum Mini"]),
    ("AUD", "electronics", "audio", "QuantumSound", (149.90, 1499.90), ["Quantum Buds Pro", "Quantum Buds Lite", "Quantum Speaker 360", "Quantum Soundbar 2.1", "Quantum Mic Studio", "Quantum Headphones Max"]),
    ("GAM", "electronics", "gaming", "QuantumPlay", (199.90, 2999.90), ["Quantum Console X", "Gamepad Quantum Pad", "Quantum Wheel Racing", "Quantum Headset Game", "Quantum Controller Mini"]),
    ("WCH", "electronics", "smartwatches", "QuantumTech", (399.90, 1899.90), ["QuantumWatch S", "QuantumWatch Pro", "QuantumWatch Fit", "QuantumWatch Ultra"]),
    ("TVS", "electronics", "televisions", "QuantumVision", (1499.90, 6499.90), ["QuantumTV 43 4K", "QuantumTV 50 4K", "QuantumTV 55 OLED", "QuantumTV 65 OLED"]),
    ("CHR", "home-office", "chairs", "QuantumWork", (499.90, 2899.90), ["Cadeira Quantum Ergo", "Cadeira Quantum Exec", "Cadeira Quantum Game", "Cadeira Quantum Compact", "Cadeira Quantum Mesh"]),
    ("DES", "home-office", "desks", "QuantumWork", (399.90, 2199.90), ["Mesa Quantum Adjust", "Mesa Quantum Compact", "Mesa Quantum Corner", "Mesa Quantum Stand"]),
    ("LMP", "home-office", "lamps", "QuantumWork", (99.90, 499.90), ["Luminária Quantum Desk", "Luminária Quantum LED", "Luminária Quantum Flex", "Luminária Quantum Ring"]),
    ("ORG", "home-office", "organizers", "QuantumWork", (49.90, 299.90), ["Organizador Quantum Mesh", "Porta-lápis Quantum Steel", "Suporte Quantum Monitor", "Gaveteiro Quantum Mini"]),
    ("SHO", "fashion", "shoes", "QuantumWear", (199.90, 699.90), ["Sapato Quantum Classic", "Sapato Quantum Oxford", "Sapato Quantum Derby", "Sapato Quantum Loaf", "Sapato Quantum Chelsea", "Sapato Quantum Formal"]),
    ("SNR", "fashion", "sneakers", "QuantumWear", (249.90, 899.90), ["Tênis Quantum Run", "Tênis Quantum Street", "Tênis Quantum Court", "Tênis Quantum Retro", "Tênis Quantum Flex", "Tênis Quantum Pro"]),
    ("TSR", "fashion", "tshirts", "QuantumWear", (49.90, 149.90), ["Camiseta Quantum Basic", "Camiseta Quantum Sport", "Camiseta Quantum Line", "Camiseta Quantum Tech", "Camiseta Quantum Slim", "Camiseta Quantum Oversize"]),
    ("JKT", "fashion", "jackets", "QuantumWear", (299.90, 899.90), ["Jaqueta Quantum Wind", "Jaqueta Quantum Urban", "Jaqueta Quantum Parka", "Jaqueta Quantum Denim"]),
    ("BAG", "fashion", "bags", "QuantumWear", (149.90, 549.90), ["Mochila Quantum City", "Bolsa Quantum Tote", "Mochila Quantum Tech", "Bolsa Quantum Crossbody"]),
    ("DRD", "fashion", "dresses", "QuantumWear", (129.90, 399.90), ["Vestido Quantum Flow", "Vestido Quantum Mini", "Vestido Quantum Maxi", "Vestido Quantum Wrap"]),
    ("BED", "home", "beds", "QuantumHome", (899.90, 3999.90), ["Cama Quantum Box", "Cama Quantum Queen", "Cama Quantum King", "Cama Quantum Pie"]),
    ("SOF", "home", "sofas", "QuantumHome", (1299.90, 4499.90), ["Sofá Quantum 3L", "Sofá Quantum 2L", "Sofá Quantum Retrátil", "Sofá Quantum Chaise"]),
    ("KIT", "home", "kitchen", "QuantumHome", (99.90, 899.90), ["Kit Facas Quantum Steel", "Panela Quantum Tripla", "Kit Utensílios Quantum", "Air Fryer Quantum 5L", "Liquidificador Quantum Pro"]),
    ("COF", "home", "coffee", "QuantumHome", (299.90, 1999.90), ["Cafeteira Quantum Drip", "Espresso Quantum 15bar", "Cafeteira Quantum Capsule", "Moedor Quantum Burr"]),
    ("LGT", "home", "lighting", "QuantumHome", (79.90, 449.90), ["Luminária Quantum Floor", "Spot Quantum LED", "Luminária Quantum Pendant", "Fita LED Quantum Smart"]),
    ("RUN", "sports", "treadmills", "QuantumFit", (1499.90, 4999.90), ["Esteira Quantum Run 100", "Esteira Quantum Run 300", "Esteira Quantum Fold"]),
    ("BIK", "sports", "bikes", "QuantumFit", (899.90, 3999.90), ["Bicicleta Quantum City", "Bicicleta Quantum MTB", "Bicicleta Quantum Road", "Bicicleta Quantum Urban"]),
    ("YOG", "sports", "yoga", "QuantumFit", (49.90, 399.90), ["Tapete Quantum Yoga", "Kit Halteres Quantum 10kg", "Faixa Quantum Resistance", "Bola Quantum Pilates"]),
    ("SKN", "beauty", "skincare", "QuantumBeauty", (39.90, 299.90), ["Sérum Quantum Glow", "Creme Quantum Hydra", "Protetor Quantum Solar", "Limpeza Quantum Ritual", "Máscara Quantum Night", "Tônico Quantum Fresh"]),
    ("FRG", "beauty", "fragrances", "QuantumBeauty", (99.90, 499.90), ["Perfume Quantum Noir", "Perfume Quantum Blanc", "Perfume Quantum Bloom", "Colônia Quantum Sport", "Perfume Quantum Ambre"]),
    ("HRC", "beauty", "hair-care", "QuantumBeauty", (29.90, 199.90), ["Shampoo Quantum Repair", "Condicionador Quantum Repair", "Óleo Quantum Argan", "Máscara Quantum Capilar", "Finalizador Quantum Fix"]),
    ("TYS", "toys", "toys", "QuantumKids", (49.90, 399.90), ["Robô Quantum Buddy", "Quebra-cabeça Quantum 500", "Boneco Quantum Hero", "Carrinho Quantum Racer", "Kit Massinha Quantum 24", "Caminhão Quantum Truck"]),
    ("GMS", "toys", "board-games", "QuantumKids", (89.90, 299.90), ["Jogo Quantum Strategy", "Jogo Quantum Party", "Jogo Quantum Family", "Jogo Quantum Quiz", "Jogo Quantum Puzzle"]),
    ("PFD", "pet", "pet-food", "QuantumPet", (39.90, 299.90), ["Ração Quantum Adult 10kg", "Ração Quantum Filhote 10kg", "Ração Quantum Light 10kg", "Petisco Quantum Premium", "Ração Quantum Gato 3kg", "Ração Quantum Castrado 3kg"]),
    ("PTA", "pet", "pet-accessories", "QuantumPet", (29.90, 249.90), ["Cama Quantum Pet M", "Coleira Quantum Pet", "Brinquedo Quantum Morde", "Caminha Quantum Luxo", "Bebedouro Quantum Pet"]),
    ("CRT", "auto", "car-tools", "QuantumAuto", (49.90, 399.90), ["OBD Quantum Scanner", "Compressor Quantum 12V", "Kit Cobertor Quantum Car", "Lavadora Quantum Pressão"]),
    ("AUT", "auto", "car-accessories", "QuantumAuto", (79.90, 599.90), ["Câmera Quantum Dash", "Suporte Quantum Phone Car", "Carregador Quantum Turbo Car", "Organizador Quantum Tronco", "Purificador Quantum Air Car"]),
]

PINNED_PRODUCTS = [
    {"sku": "QTM-NBK-00123", "name": "Notebook QuantumBook Pro 14", "category": "electronics", "subcategory": "notebooks", "brand": "QuantumTech", "price": 7499.90, "rating": 4.7},
    {"sku": "QTM-ACC-00017", "name": "Mouse Quantum Air", "category": "electronics", "subcategory": "accessories", "brand": "QuantumTech", "price": 399.90, "rating": 4.6},
    {"sku": "QTM-NBK-00150", "name": "Notebook QuantumBook Air 13", "category": "electronics", "subcategory": "notebooks", "brand": "QuantumTech", "price": 4499.90, "rating": 4.5},
    {"sku": "QTM-ACC-00100", "name": "Mouse Quantum Click", "category": "electronics", "subcategory": "accessories", "brand": "QuantumTech", "price": 89.90, "rating": 4.3},
]

POLICIES = [
    {"id": "POL-RETURN-001", "category": "returns", "title": "Política de devolução padrão", "country": "BR", "content": "Produtos podem ser devolvidos em até 30 dias corridos após a entrega, sem custo para o cliente. O item deve estar sem uso, com embalagem original e protocolo de devolução gerado."},
    {"id": "POL-RETURN-002", "category": "returns", "title": "Política de devolución estándar", "country": "MX", "content": "Los productos pueden devolverse hasta 30 días naturales después de la entrega, sin costo para el cliente."},
    {"id": "POL-RETURN-003", "category": "returns", "title": "Política de devolución Argentina", "country": "AR", "content": "Los productos pueden devolverse dentro de los 10 días corridos posteriores a la entrega según normativa local."},
    {"id": "POL-RETURN-004", "category": "returns", "title": "Política de devolución Colombia", "country": "CO", "content": "Los productos pueden devolverse dentro de los 15 días calendario posteriores a la entrega."},
    {"id": "POL-RETURN-005", "category": "returns", "title": "Política de devolución Chile", "country": "CL", "content": "Los productos pueden devolverse hasta 30 días corridos después de la entrega."},
    {"id": "POL-RETURN-006", "category": "returns", "title": "Política de devolução Portugal", "country": "PT", "content": "Os produtos podem ser devolvidos até 14 dias após a entrega, em conformidade com a legislação europeia."},
    {"id": "POL-RETURN-007", "category": "returns", "title": "Standard return policy", "country": "US", "content": "Products may be returned within 30 days of delivery for a full refund."},
    {"id": "POL-REFUND-001", "category": "refund", "title": "Política de reembolso padrão", "country": "BR", "content": "Reembolsos são processados em até 7 dias úteis após a confirmação da devolução. Valores acima do limite de aprovação automática exigem aprovação humana."},
    {"id": "POL-REFUND-002", "category": "refund", "title": "Política de reembolso México", "country": "MX", "content": "Los reembolsos se procesan en un plazo máximo de 10 días hábiles después de recibir el producto."},
    {"id": "POL-SHIP-001", "category": "shipping", "title": "Política de entrega padrão", "country": "BR", "content": "Entregas em capitais em até 2 dias úteis, demais localidades em até 7 dias úteis. Pedidos acima de R$ 299 têm frete grátis."},
    {"id": "POL-SHIP-002", "category": "shipping", "title": "Política de entrega expressa", "country": "BR", "content": "Entrega expressa em até 1 dia útil para capitais, sujeita a disponibilidade de estoque no centro de distribuição mais próximo."},
    {"id": "POL-SHIP-003", "category": "shipping", "title": "Política de envío México", "country": "MX", "content": "Envíos a ciudades principales en 2 a 4 días hábiles. Envío gratuito en pedidos superiores a MXN 1,200."},
    {"id": "POL-WARRANTY-001", "category": "warranty", "title": "Garantia padrão de produtos", "country": "BR", "content": "Garantia de 90 dias para defeitos de fabricação em todos os produtos. Eletrônicos da marca QuantumTech possuem garantia estendida de 12 meses."},
    {"id": "POL-WARRANTY-002", "category": "warranty", "title": "Garantia estendida eletrônicos", "country": "BR", "content": "Eletrônicos QuantumTech contam com garantia estendida de 12 meses mediante registro do produto em até 30 dias após a compra."},
    {"id": "POL-FRAUD-001", "category": "fraud", "title": "Política antifraude", "country": "BR", "content": "Compras com comportamento suspeito podem ser retidas para análise manual. O cliente é notificado e o pedido é liberado após confirmação de identidade."},
    {"id": "POL-FRAUD-002", "category": "fraud", "title": "Política antifraude México", "country": "MX", "content": "Las compras sospechosas se retienen para revisión manual y se notifica al cliente por correo."},
    {"id": "POL-PRICE-001", "category": "price_match", "title": "Política de match de preço", "country": "BR", "content": "Se o cliente encontrar o mesmo produto por preço menor em loja parceira, a Quantum iguala o valor em até 48 horas após a compra."},
    {"id": "POL-PRICE-002", "category": "price_match", "title": "Price match premium", "country": "BR", "content": "Clientes dos segmentos premium e platinum têm direito a match de preço em até 7 dias após a compra."},
    {"id": "POL-CANCEL-001", "category": "cancellation", "title": "Política de cancelamento", "country": "BR", "content": "Pedidos podem ser cancelados sem custo antes do despacho. Após o despacho, o cancelamento segue o fluxo de devolução padrão."},
    {"id": "POL-CANCEL-002", "category": "cancellation", "title": "Política de cancelamiento México", "country": "MX", "content": "Los pedidos pueden cancelarse sin costo antes del envío. Después del envío aplica la política de devolución."},
]

SUPPORT_CATEGORIES = ["delivery", "return", "refund", "payment", "product", "warranty", "account", "fraud", "other"]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_customers(rng: random.Random) -> list[dict]:
    customers = []
    for customer_id, overrides in PINNED_CUSTOMERS.items():
        row = {
            "id": customer_id,
            "name": overrides["name"],
            "email": overrides["email"],
            "country": overrides["country"],
            "city": overrides["city"],
            "segment": overrides["segment"],
            "loyalty_tier": overrides["loyalty_tier"],
            "customer_since": overrides["customer_since"],
            "lifetime_value": overrides["lifetime_value"],
            "preferred_channel": overrides["preferred_channel"],
            "total_orders": overrides["total_orders"],
        }
        customers.append(row)
    channels = ["whatsapp", "chat", "email", "phone", "web"]
    available_names = list(zip(FIRST_NAMES, LAST_NAMES, strict=False))
    rng.shuffle(available_names)
    segments = (["premium"] * 8 + ["budget"] * 15 + ["standard"] * 30)
    for index in range(39):
        customer_id = f"CUS-{1012 + index}"
        first, last = available_names[index]
        email = f"{first.lower()}.{last.lower()}@example.com"
        country = rng.choices(
            ["BR", "BR", "BR", "BR", "BR", "BR", "MX", "AR", "CO", "CL", "PT", "US"],
            k=1,
        )[0]
        city = rng.choice(COUNTRY_CITIES[country])
        segment = segments[index]
        tier_by_segment = {
            "premium": rng.choices(["platinum", "gold", "gold", "silver"], k=1)[0],
            "standard": rng.choices(["gold", "silver", "silver", "bronze", "bronze", "none"], k=1)[0],
            "budget": rng.choices(["bronze", "none", "none"], k=1)[0],
        }[segment]
        since_year = rng.randint(2019, 2026)
        since_month = rng.randint(1, 12)
        since_day = min(rng.randint(1, 28), 28)
        ltv_by_segment = {
            "premium": round(rng.uniform(8000, 20000), 2),
            "standard": round(rng.uniform(1500, 8000), 2),
            "budget": round(rng.uniform(200, 1500), 2),
        }[segment]
        total_orders = max(rng.randint(1, 40), rng.randint(1, 8))
        customers.append({
            "id": customer_id,
            "name": f"{first} {last}",
            "email": email,
            "country": country,
            "city": city,
            "segment": segment,
            "loyalty_tier": tier_by_segment,
            "customer_since": date(since_year, since_month, since_day),
            "lifetime_value": ltv_by_segment,
            "preferred_channel": rng.choice(channels),
            "total_orders": total_orders,
        })
    return customers


def _build_products(rng: random.Random) -> list[dict]:
    products = [dict(product) | {"currency": "BRL", "active": True} for product in PINNED_PRODUCTS]
    sku_counter = 1000
    for code, category, subcategory, brand, (price_lo, price_hi), models in PRODUCT_LINES:
        for model in models:
            sku_counter += 1
            products.append({
                "sku": f"QTM-{code}-{sku_counter:05d}",
                "name": model,
                "category": category,
                "subcategory": subcategory,
                "brand": brand,
                "price": round(rng.uniform(price_lo, price_hi), 2),
                "currency": "BRL",
                "active": rng.random() > 0.03,
                "rating": round(rng.uniform(3.5, 4.9), 1),
            })
    return products


def _build_inventory(rng: random.Random, products: list[dict]) -> list[dict]:
    items = []
    pinned_inventory = {
        "QTM-NBK-00123": [
            {"warehouse_id": "BR-SP-01", "city": "São Paulo", "country": "BR", "available": 21, "reserved": 4},
            {"warehouse_id": "BR-RJ-01", "city": "Rio de Janeiro", "country": "BR", "available": 16, "reserved": 2},
        ],
        "QTM-NBK-00150": [],
        "QTM-ACC-00100": [
            {"warehouse_id": "BR-SP-01", "city": "São Paulo", "country": "BR", "available": 2, "reserved": 0},
        ],
    }
    for product in products:
        sku = product["sku"]
        if sku in pinned_inventory:
            for row in pinned_inventory[sku]:
                items.append({"sku": sku, **row})
            continue
        warehouse_indexes = rng.sample(range(len(WAREHOUSES)), k=rng.randint(1, 3))
        for warehouse_index in warehouse_indexes:
            warehouse = WAREHOUSES[warehouse_index]
            available = rng.randint(1, 120)
            reserved = rng.randint(0, min(12, available // 3))
            items.append({
                "sku": sku,
                "warehouse_id": warehouse["warehouse_id"],
                "city": warehouse["city"],
                "country": warehouse["country"],
                "available": available,
                "reserved": reserved,
            })
    return items


def _shipment_events(order_id: str, created_at: datetime, status: str, last_update: datetime, delay_description: str | None = None) -> list[dict]:
    events = [{"timestamp": _iso(created_at), "location": "Centro de distribuição", "status": "order_placed", "description": "Pedido recebido e confirmado"}]
    if status in ("shipped", "in_transit", "delivered", "awaiting_pickup", "delayed", "lost", "cancelled"):
        events.append({"timestamp": _iso(created_at + timedelta(days=1)), "location": "Centro de distribuição", "status": "picked_up", "description": "Coletado pela transportadora"})
    if status in ("in_transit", "delivered", "delayed", "lost"):
        events.append({"timestamp": _iso(created_at + timedelta(days=3)), "location": "Hub de São Paulo", "status": "in_transit", "description": "Em trânsito para unidade de destino"})
    if status == "delivered":
        events.append({"timestamp": _iso(last_update), "location": "Residência do cliente", "status": "delivered", "description": "Pacote entregue ao cliente"})
    elif status == "delayed":
        description = delay_description or "Atraso devido a condições climáticas na rota de entrega"
        events.append({"timestamp": _iso(last_update - timedelta(hours=4)), "location": "Hub de São Paulo", "status": "delayed", "description": description})
    elif status == "lost":
        events.append({"timestamp": _iso(last_update - timedelta(hours=6)), "location": "Centro de triagem", "status": "lost", "description": "Pacote não localizado no centro de triagem"})
    elif status == "cancelled":
        events.append({"timestamp": _iso(last_update), "location": "Centro de distribuição", "status": "cancelled", "description": "Envio cancelado a pedido do cliente"})
    elif status == "awaiting_pickup":
        events.append({"timestamp": _iso(last_update), "location": "Agência Quantum Logistics", "status": "awaiting_pickup", "description": "Aguardando retirada pelo cliente na agência"})
    elif status == "shipped":
        events.append({"timestamp": _iso(last_update), "location": "Centro de distribuição", "status": "shipped", "description": "Pacote despachado com sucesso"})
    return events


def _build_orders_and_shipments(rng: random.Random, customers: list[dict], products: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    customer_ids = [customer["id"] for customer in customers]
    sku_by_id = {product["sku"]: product for product in products}

    pinned_shipments = {
        "ORD-2026-10001": {
            "shipment_id": "SHP-87421", "carrier": "Quantum Logistics", "status": "in_transit",
            "tracking_code": "QTM982734BR", "estimated_delivery": date(2026, 9, 14),
            "last_update": datetime(2026, 9, 12, 22, 15, tzinfo=UTC),
        },
        "ORD-2026-10005": {
            "shipment_id": "SHP-90010", "carrier": "Quantum Logistics", "status": "delivered",
            "tracking_code": "QTM301118BR", "estimated_delivery": date(2026, 9, 1),
            "last_update": datetime(2026, 9, 1, 14, 40, tzinfo=UTC),
        },
        "ORD-2026-10007": {
            "shipment_id": "SHP-90020", "carrier": "Quantum Logistics", "status": "delivered",
            "tracking_code": "QTM662904BR", "estimated_delivery": date(2026, 7, 25),
            "last_update": datetime(2026, 7, 25, 11, 20, tzinfo=UTC),
        },
        "ORD-2026-10010": {
            "shipment_id": "SHP-90030", "carrier": "Quantum Logistics", "status": "delivered",
            "tracking_code": "QTM521773BR", "estimated_delivery": date(2026, 8, 31),
            "last_update": datetime(2026, 8, 31, 9, 55, tzinfo=UTC),
        },
        "ORD-2026-10012": {
            "shipment_id": "SHP-90040", "carrier": "Expresso Norte", "status": "delivered",
            "tracking_code": "QTM444012BR", "estimated_delivery": date(2026, 9, 5),
            "last_update": datetime(2026, 9, 5, 16, 10, tzinfo=UTC),
        },
        "ORD-2026-10014": {
            "shipment_id": "SHP-90050", "carrier": "Quantum Logistics", "status": "shipped",
            "tracking_code": "QTM909876BR", "estimated_delivery": date(2026, 9, 15),
            "last_update": datetime(2026, 9, 12, 10, 0, tzinfo=UTC),
        },
        "ORD-2026-10023": {
            "shipment_id": "SHP-90045", "carrier": "Quantum Logistics", "status": "delayed",
            "tracking_code": "QTM453128BR", "estimated_delivery": date(2026, 9, 9),
            "last_update": datetime(2026, 9, 13, 8, 30, tzinfo=UTC),
        },
        "ORD-2026-10024": {
            "shipment_id": "SHP-90051", "carrier": "Quantum Logistics", "status": "lost",
            "tracking_code": "QTM774910BR", "estimated_delivery": date(2026, 9, 8),
            "last_update": datetime(2026, 9, 12, 18, 5, tzinfo=UTC),
        },
        "ORD-2026-10025": {
            "shipment_id": "SHP-90060", "carrier": "Quantum Logistics", "status": "cancelled",
            "tracking_code": "QTM337215BR", "estimated_delivery": date(2026, 9, 10),
            "last_update": datetime(2026, 9, 7, 13, 25, tzinfo=UTC),
        },
        "ORD-2026-10030": {
            "shipment_id": "SHP-90077", "carrier": "Quantum Logistics", "status": "delayed",
            "tracking_code": "QTM118736BR", "estimated_delivery": date(2026, 9, 10),
            "last_update": datetime(2026, 9, 12, 21, 45, tzinfo=UTC),
        },
    }

    pinned_orders = {
        "ORD-2026-10001": {"customer_id": "CUS-1001", "status": "in_transit", "created_at": datetime(2026, 9, 2, 13, 42, tzinfo=UTC), "items": [("QTM-NBK-00123", 1), ("QTM-ACC-00017", 1)]},
        "ORD-2026-10005": {"customer_id": "CUS-1001", "status": "delivered", "created_at": datetime(2026, 8, 20, 10, 5, tzinfo=UTC), "items": [("QTM-AUD-01023", 1), ("QTM-CHR-01042", 1)]},
        "ORD-2026-10007": {"customer_id": "CUS-1001", "status": "delivered", "created_at": datetime(2026, 7, 2, 16, 20, tzinfo=UTC), "items": [("QTM-BED-01089", 1)]},
        "ORD-2026-10010": {"customer_id": "CUS-1002", "status": "delivered", "created_at": datetime(2026, 8, 25, 9, 0, tzinfo=UTC), "items": [("QTM-PHN-01005", 1)]},
        "ORD-2026-10012": {"customer_id": "CUS-1002", "status": "delivered", "created_at": datetime(2026, 9, 1, 14, 30, tzinfo=UTC), "items": [("QTM-ACC-00017", 1)]},
        "ORD-2026-10014": {"customer_id": "CUS-1001", "status": "shipped", "created_at": datetime(2026, 9, 8, 11, 15, tzinfo=UTC), "items": [("QTM-COF-01102", 1), ("QTM-LMP-01051", 2)]},
        "ORD-2026-10023": {"customer_id": "CUS-1007", "status": "delayed", "created_at": datetime(2026, 8, 30, 8, 45, tzinfo=UTC), "items": [("QTM-NBK-01001", 1), ("QTM-BAG-01081", 1)]},
        "ORD-2026-10024": {"customer_id": "CUS-1005", "status": "lost", "created_at": datetime(2026, 8, 28, 19, 10, tzinfo=UTC), "items": [("QTM-WCH-01034", 1)]},
        "ORD-2026-10025": {"customer_id": "CUS-1003", "status": "cancelled", "created_at": datetime(2026, 9, 5, 12, 0, tzinfo=UTC), "items": [("QTM-SOF-01093", 1)]},
        "ORD-2026-10030": {"customer_id": "CUS-1011", "status": "delayed", "created_at": datetime(2026, 9, 1, 20, 35, tzinfo=UTC), "items": [("QTM-TVS-01038", 1)]},
    }

    orders: list[dict] = []
    orders_items: list[dict] = []
    shipments: list[dict] = []

    for order_id in sorted(pinned_orders):
        spec = pinned_orders[order_id]
        items = []
        total = 0.0
        for sku, quantity in spec["items"]:
            product = sku_by_id[sku]
            unit_price = product["price"]
            items.append({"order_id": order_id, "sku": sku, "name": product["name"], "quantity": quantity, "unit_price": unit_price})
            total += unit_price * quantity
        orders.append({
            "id": order_id, "customer_id": spec["customer_id"], "status": spec["status"],
            "created_at": spec["created_at"], "total": round(total, 2), "currency": "BRL",
        })
        orders_items.extend(items)
        shipment = pinned_shipments.get(order_id)
        if shipment is not None:
            delay_description = None
            if order_id == "ORD-2026-10030":
                delay_description = "Falha na transportadora: veículo com problema mecânico na rota de entrega"
            events = _shipment_events(order_id, spec["created_at"], shipment["status"], shipment["last_update"], delay_description)
            shipments.append({"order_id": order_id, **shipment, "events": events})

    remaining_statuses = (
        ["delivered"] * 35 + ["in_transit"] * 16 + ["shipped"] * 6 + ["delayed"] * 3
        + ["awaiting_pickup"] * 3 + ["cancelled"] * 4 + ["pending"] * 6 + ["confirmed"] * 8
    )
    rng.shuffle(remaining_statuses)
    order_number = 10031
    shipment_number = 90091
    sku_list = list(sku_by_id)
    for status in remaining_statuses:
        order_id = f"ORD-2026-{order_number}"
        order_number += 1
        customer_id = rng.choice(customer_ids)
        created_at = datetime(2026, 9, 13, tzinfo=UTC) - timedelta(days=rng.randint(2, 45), hours=rng.randint(0, 20))
        item_count = rng.randint(1, 3)
        item_skus = rng.sample(sku_list, k=item_count)
        items = []
        total = 0.0
        for sku in item_skus:
            product = sku_by_id[sku]
            quantity = rng.randint(1, 2)
            items.append({"order_id": order_id, "sku": sku, "name": product["name"], "quantity": quantity, "unit_price": product["price"]})
            total += product["price"] * quantity
        orders.append({"id": order_id, "customer_id": customer_id, "status": status, "created_at": created_at, "total": round(total, 2), "currency": "BRL"})
        orders_items.extend(items)
        if status in ("delivered", "in_transit", "shipped", "delayed", "awaiting_pickup", "cancelled"):
            shipment_id = f"SHP-{shipment_number}"
            shipment_number += 1
            if status == "delivered":
                delivered_at = created_at + timedelta(days=rng.randint(4, 9))
                estimated = delivered_at.date()
            elif status == "delayed":
                estimated = (created_at + timedelta(days=7)).date()
                delivered_at = created_at + timedelta(days=10, hours=rng.randint(0, 12))
            elif status == "in_transit":
                estimated = (created_at + timedelta(days=10)).date()
                delivered_at = created_at + timedelta(days=5, hours=rng.randint(0, 12))
            else:
                estimated = (created_at + timedelta(days=5)).date()
                delivered_at = created_at + timedelta(days=1, hours=rng.randint(0, 12))
            carrier = "Quantum Logistics" if rng.random() > 0.15 else "Expresso Norte"
            tracking = f"QTM{rng.randint(100000, 999999)}BR"
            events = _shipment_events(order_id, created_at, status, delivered_at)
            shipments.append({
                "order_id": order_id,
                "shipment_id": shipment_id,
                "carrier": carrier,
                "status": status,
                "tracking_code": tracking,
                "estimated_delivery": estimated,
                "last_update": delivered_at,
                "events": events,
            })
    return orders, orders_items, shipments


def _build_cases(rng: random.Random, customers: list[dict]) -> list[dict]:
    cases = []
    pinned_cases = {
        "CASE-2026-1001": {"customer_id": "CUS-1001", "category": "delivery", "summary": "Pedido não chegou", "description": "Pedido ORD-2026-10014 está em trânsito há mais tempo que o esperado.", "status": "open", "priority": "P2"},
        "CASE-2026-1002": {"customer_id": "CUS-1010", "category": "account", "summary": "Erro de cobrança no cartão", "description": "Identifiquei duas cobranças para o mesmo pedido no cartão de crédito.", "status": "open", "priority": "P1"},
    }
    for case_id, spec in pinned_cases.items():
        created = datetime(2026, 9, 12, 9, 0, tzinfo=UTC)
        cases.append({
            "case_id": case_id,
            "protocol": f"QCS-{case_id.split('-')[-1]}",
            **spec,
            "lab_group": "system",
            "created_at": created,
            "updated_at": created + timedelta(hours=1),
        })
    categories = SUPPORT_CATEGORIES
    statuses = ["open", "open", "in_progress", "resolved", "closed", "waiting_customer", "resolved", "closed"]
    for index in range(18):
        case_id = f"CASE-2026-100{3 + index}"
        created = datetime(2026, 9, 13, tzinfo=UTC) - timedelta(days=rng.randint(0, 15), hours=rng.randint(0, 20))
        status = statuses[rng.randrange(len(statuses))]
        cases.append({
            "case_id": case_id,
            "protocol": f"QCS-{1003 + index}",
            "customer_id": rng.choice(customers)["id"],
            "category": rng.choice(categories),
            "summary": "Atendimento registrado pela equipe Quantum",
            "description": "Caso fictício para laboratório didático.",
            "status": status,
            "priority": rng.choice(["P1", "P2", "P3", "P4"]),
            "lab_group": "system",
            "created_at": created,
            "updated_at": created + timedelta(hours=6) if status in ("in_progress", "waiting_customer", "resolved", "closed") else created,
        })
    return cases


def _build_returns(rng: random.Random, orders: list[dict], orders_items: list[dict]) -> list[dict]:
    order_by_id = {order["id"]: order for order in orders}
    item_by_order = {}
    for item in orders_items:
        item_by_order.setdefault(item["order_id"], []).append(item)

    pinned_returns = {
        "RET-90001": {"customer_id": "CUS-1001", "order_id": "ORD-2026-10005", "sku": "QTM-AUD-01023", "reason": "Produto incompatível com minha necessidade", "status": "requested", "created_at": datetime(2026, 9, 3, 14, 0, tzinfo=UTC)},
        "RET-90002": {"customer_id": "CUS-1001", "order_id": "ORD-2026-10007", "sku": "QTM-BED-01089", "reason": "Produto chegou fora do prazo estipulado", "status": "rejected", "created_at": datetime(2026, 7, 26, 10, 0, tzinfo=UTC)},
    }
    returns = []
    for return_id, spec in pinned_returns.items():
        returns.append({"return_id": return_id, "protocol": f"QRET-2026-{return_id.split('-')[-1]}", **spec, "lab_group": "system"})
    delivered_orders = [order for order in orders if order["status"] == "delivered" and order["id"] not in {"ORD-2026-10005", "ORD-2026-10007"}]
    statuses = ["requested", "approved", "awaiting_item", "received", "refunded", "refunded", "approved", "received"]
    return_number = 90003
    for return_index in range(13):
        order = rng.choice(delivered_orders)
        items = item_by_order.get(order["id"], [])
        if not items:
            continue
        item = rng.choice(items)
        return_id = f"RET-{return_number}"
        return_number += 1
        returns.append({
            "return_id": return_id,
            "protocol": f"QRET-2026-{return_id.split('-')[-1]}",
            "customer_id": order["customer_id"],
            "order_id": order["id"],
            "sku": item["sku"],
            "reason": rng.choice(["Produto apresentou defeito", "Arrependimento da compra", "Produto diferente do anunciado", "Não gostei do produto"]),
            "status": statuses[rng.randrange(len(statuses))],
            "lab_group": "system",
            "created_at": datetime(2026, 9, 10, 8, 0, tzinfo=UTC) + timedelta(days=return_index, hours=return_index % 6),
        })
    return returns


def _build_approvals(rng: random.Random) -> list[dict]:
    approvals = []
    pinned = {
        "APR-1001": {"type": "refund", "reference_id": "ORD-2026-10001", "requested_by": "ai-agent", "amount": 7499.90, "reason": "Refund requested after delivery issue", "status": "pending"},
        "APR-1002": {"type": "refund", "reference_id": "ORD-2026-10001", "requested_by": "ai-agent", "amount": 7499.90, "reason": "Refund requested after delivery issue", "status": "approved", "decision": "approved", "comment": "Approved by operations supervisor", "decided_by": "supervisor.ops@quantum.example"},
    }
    for approval_id, spec in pinned.items():
        approvals.append({"approval_id": approval_id, **spec, "lab_group": "system", "created_at": datetime(2026, 9, 13, 15, 0, tzinfo=UTC), "decided_at": datetime(2026, 9, 13, 15, 30, tzinfo=UTC) if spec["status"] == "approved" else None})
    types = ["refund", "goodwill", "return_override", "fraud_review", "refund"]
    statuses = ["pending", "approved", "rejected", "pending", "approved"]
    for index in range(8):
        approval_id = f"APR-{1003 + index}"
        created = datetime(2026, 9, 13, tzinfo=UTC) - timedelta(days=rng.randint(0, 6), hours=rng.randint(0, 12))
        status = rng.choice(statuses)
        approvals.append({
            "approval_id": approval_id,
            "type": rng.choice(types),
            "reference_id": f"ORD-2026-{10000 + rng.randint(1, 100)}",
            "requested_by": rng.choice(["ai-agent", "n8n-workflow", "dify-agent"]),
            "amount": round(rng.uniform(50, 8000), 2),
            "reason": rng.choice(["Refund requested after delay", "Goodwill credit for loyal customer", "Override return window", "Fraud review escalation"]),
            "status": status,
            "decision": status if status != "pending" else None,
            "comment": "Reviewed by operations team" if status != "pending" else None,
            "decided_by": "supervisor.ops@quantum.example" if status != "pending" else None,
            "lab_group": "system",
            "created_at": created,
            "decided_at": created + timedelta(hours=2) if status != "pending" else None,
        })
    return approvals


def _build_refunds() -> list[dict]:
    created_at = datetime(2026, 9, 11, 15, 0, tzinfo=UTC)
    return [
        {"refund_id": "REF-10005", "order_id": "ORD-2026-10012", "amount": 399.90, "reason": "delivery_issue", "approval_id": None, "status": "processing", "lab_group": "system", "created_at": created_at},
        {"refund_id": "REF-10006", "order_id": "ORD-2026-10001", "amount": 7499.90, "reason": "delivery_issue", "approval_id": "APR-1002", "status": "processing", "lab_group": "system", "created_at": created_at - timedelta(days=1)},
    ]


def _build_promotions() -> list[dict]:
    return [
        {"promotion_id": "PROMO-100", "name": "Quantum Premium Week", "description": "10% off em produtos de eletrônicos acima de R$ 500.", "discount_pct": 10.0, "category": "electronics", "brand": None, "country": "BR", "min_price": 500.0, "active": True, "starts_at": date(2026, 9, 1), "ends_at": date(2026, 9, 30)},
        {"promotion_id": "PROMO-101", "name": "Quantum Fashion Friday", "description": "20% off em moda selecionada.", "discount_pct": 20.0, "category": "fashion", "brand": None, "country": "BR", "min_price": None, "active": True, "starts_at": date(2026, 9, 10), "ends_at": date(2026, 10, 5)},
        {"promotion_id": "PROMO-102", "name": "Home & Office Days", "description": "15% off em home-office.", "discount_pct": 15.0, "category": "home-office", "brand": None, "country": "BR", "min_price": 200.0, "active": True, "starts_at": date(2026, 9, 5), "ends_at": date(2026, 9, 20)},
        {"promotion_id": "PROMO-103", "name": "QuantumFit Summer", "description": "12% off em artigos esportivos.", "discount_pct": 12.0, "category": "sports", "brand": None, "country": "BR", "min_price": None, "active": True, "starts_at": date(2026, 9, 1), "ends_at": date(2026, 10, 1)},
        {"promotion_id": "PROMO-104", "name": "Beauty Essentials", "description": "18% off em beleza.", "discount_pct": 18.0, "category": "beauty", "brand": None, "country": "BR", "min_price": 50.0, "active": True, "starts_at": date(2026, 9, 8), "ends_at": date(2026, 9, 28)},
        {"promotion_id": "PROMO-105", "name": "QuantumTech Brand Week", "description": "8% off em produtos da marca QuantumTech.", "discount_pct": 8.0, "category": None, "brand": "QuantumTech", "country": "BR", "min_price": 100.0, "active": True, "starts_at": date(2026, 9, 12), "ends_at": date(2026, 10, 12)},
    ]


def _build_interactions(customers: list[dict]) -> list[dict]:
    customer_ids = [customer["id"] for customer in customers]
    pinned = [
        {"customer_id": "CUS-1001", "channel": "chat", "message": "Meu pedido não chegou", "response": "Identificamos atraso na transportadora e abrimos um caso de atendimento para acompanhamento.", "source": "ai-agent"},
        {"customer_id": "CUS-1001", "channel": "whatsapp", "message": "Quero devolver o tênis que comprei", "response": "Verificamos sua elegibilidade e geramos o protocolo de devolução QRET-2026-90001.", "source": "dify-agent"},
        {"customer_id": "CUS-1007", "channel": "chat", "message": "Meu pedido está atrasado e é urgente", "response": "Confirmamos o atraso e priorizamos seu caso como P1 com SLA de 2 horas.", "source": "ai-agent"},
        {"customer_id": "CUS-1010", "channel": "email", "message": "Erro de cobrança no cartão", "response": "Encaminhamos para análise antifraude e criamos o caso CASE-2026-1002.", "source": "ai-agent"},
        {"customer_id": "CUS-1005", "channel": "chat", "message": "Cadê meu pacote?", "response": "A transportadora não localizou o pacote. Iniciamos o processo de ressarcimento.", "source": "n8n-workflow"},
    ]
    generated = [
        {"customer_id": customer_ids[i], "channel": channel, "message": "Interação registrada em laboratório didático", "response": "Resposta automática simulada pela plataforma Quantum.", "source": source}
        for i, (channel, source) in enumerate([("web", "dify-agent"), ("chat", "ai-agent"), ("whatsapp", "n8n-workflow"), ("phone", "human-agent"), ("email", "ai-agent")] * 2)
        if i < 7
    ]
    interactions = []
    for index, base in enumerate(pinned + generated):
        interaction = {"interaction_id": f"INT-{10001 + index}", "lab_group": "system", **base}
        interaction["created_at"] = TODAY - timedelta(days=(len(pinned + generated) - index) % 12, hours=9 + index % 8)
        interactions.append(interaction)
    return interactions


def _build_events(customers: list[dict]) -> list[dict]:
    return [
        {"event_type": "customer_lookup", "customer_id": "CUS-1001", "resource_type": "customer", "resource_id": "CUS-1001", "metadata": {"source": "n8n", "action": "get"}},
        {"event_type": "order_lookup", "customer_id": "CUS-1001", "resource_type": "order", "resource_id": "ORD-2026-10001", "metadata": {"source": "ai-agent", "action": "get"}},
        {"event_type": "shipment_lookup", "customer_id": "CUS-1001", "resource_type": "shipment", "resource_id": "SHP-87421", "metadata": {"source": "ai-agent", "order_id": "ORD-2026-10001"}},
        {"event_type": "inventory_lookup", "customer_id": None, "resource_type": "inventory", "resource_id": "QTM-NBK-00123", "metadata": {"source": "dify-agent", "action": "get"}},
        {"event_type": "support_case_created", "customer_id": "CUS-1001", "resource_type": "support_case", "resource_id": "CASE-2026-1001", "metadata": {"source": "ai-agent", "priority": "P2"}},
    ]


def seed_data() -> None:
    db = SessionLocal()
    try:
        customer_exists = db.execute(select(Customer.id).limit(1)).scalar_one_or_none()
        if customer_exists:
            return

        rng = random.Random(QUANTUM_SEED)

        customers = _build_customers(rng)
        db.add_all(Customer(**customer) for customer in customers)

        products = _build_products(rng)
        db.add_all(Product(**product) for product in products)

        inventory = _build_inventory(rng, products)
        db.add_all(InventoryItem(**item) for item in inventory)

        orders, orders_items, shipments = _build_orders_and_shipments(rng, customers, products)
        db.add_all(Order(**order) for order in orders)
        db.add_all(OrderItem(**item) for item in orders_items)
        db.add_all(Shipment(**shipment) for shipment in shipments)

        policy_rows = [{**policy, "effective_from": date(2026, 1, 1)} for policy in POLICIES]
        db.add_all(Policy(**policy) for policy in policy_rows)

        cases = _build_cases(rng, customers)
        for case in cases:
            db.add(SupportCase(**case))

        returns = _build_returns(rng, orders, orders_items)
        db.add_all(ReturnRecord(**return_record) for return_record in returns)

        approvals = _build_approvals(rng)
        db.add_all(Approval(**approval) for approval in approvals)

        refunds = _build_refunds()
        db.add_all(Refund(**refund) for refund in refunds)

        promotions = _build_promotions()
        db.add_all(Promotion(**promotion) for promotion in promotions)

        interactions = _build_interactions(customers)
        for interaction in interactions:
            db.add(Interaction(**interaction))

        for index, event in enumerate(_build_events(customers)):
            db.add(Event(
                event_id=f"EV-SEED-{index + 1:04d}",
                event_type=event["event_type"],
                lab_group="system",
                customer_id=event["customer_id"],
                timestamp=datetime(2026, 9, 13, 12, 0, tzinfo=UTC) - timedelta(hours=index * 3),
                resource_type=event["resource_type"],
                resource_id=event["resource_id"],
                metadata_json=json.dumps(event["metadata"], ensure_ascii=False, sort_keys=True),
            ))

        db.commit()
        logger.info(
            "Quantum Commerce seed complete: %d customers, %d products, %d orders, %d shipments, %d policies, %d cases, %d returns, %d approvals",
            len(customers), len(products), len(orders), len(shipments), len(POLICIES), len(cases), len(returns), len(approvals),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()