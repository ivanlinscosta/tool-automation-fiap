import logging

from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.employee import Employee
from app.models.team import Team


logger = logging.getLogger(__name__)

TEAMS = {
    "it": {"category": "it", "team": "IT Support", "email": "it@example.com", "queue": "technical-support", "sla_default_hours": 4},
    "hr": {"category": "hr", "team": "Human Resources", "email": "hr@example.com", "queue": "employee-services", "sla_default_hours": 8},
    "finance": {"category": "finance", "team": "Finance", "email": "finance@example.com", "queue": "financial-operations", "sla_default_hours": 12},
    "facilities": {"category": "facilities", "team": "Facilities", "email": "facilities@example.com", "queue": "facility-maintenance", "sla_default_hours": 6},
    "security": {"category": "security", "team": "Security", "email": "security@example.com", "queue": "security-operations", "sla_default_hours": 2},
    "other": {"category": "other", "team": "General Support", "email": "support@example.com", "queue": "general-inquiries", "sla_default_hours": 24},
}

EMPLOYEES = [
    {"id": "EMP001", "name": "Ayla Mercer", "department": "Marketing", "email": "ayla.mercer@example.com", "role": "Analista", "vip": False},
    {"id": "EMP002", "name": "Dario Flint", "department": "IT", "email": "dario.flint@example.com", "role": "Desenvolvedor", "vip": True},
    {"id": "EMP003", "name": "Lina Vale", "department": "Finance", "email": "lina.vale@example.com", "role": "Analista Senior", "vip": False},
    {"id": "EMP004", "name": "Nico Rowan", "department": "HR", "email": "nico.rowan@example.com", "role": "Coordenador", "vip": False},
    {"id": "EMP005", "name": "Mira Solis", "department": "Facilities", "email": "mira.solis@example.com", "role": "Assistente", "vip": False},
    {"id": "EMP006", "name": "Theo Ravel", "department": "Security", "email": "theo.ravel@example.com", "role": "Técnico", "vip": True},
    {"id": "EMP007", "name": "Iris Calder", "department": "Legal", "email": "iris.calder@example.com", "role": "Gerente", "vip": False},
    {"id": "EMP008", "name": "Caio Ember", "department": "Sales", "email": "caio.ember@example.com", "role": "Analista", "vip": False},
    {"id": "EMP009", "name": "Sena Marlow", "department": "Operations", "email": "sena.marlow@example.com", "role": "Diretor", "vip": True},
    {"id": "EMP010", "name": "Elio Voss", "department": "R&D", "email": "elio.voss@example.com", "role": "Designer", "vip": False},
    {"id": "EMP011", "name": "Talia Wynn", "department": "Marketing", "email": "talia.wynn@example.com", "role": "Estagiário", "vip": False},
    {"id": "EMP012", "name": "Breno Quill", "department": "IT", "email": "breno.quill@example.com", "role": "Técnico", "vip": False},
    {"id": "EMP013", "name": "Celia North", "department": "Finance", "email": "celia.north@example.com", "role": "Assistente", "vip": False},
    {"id": "EMP014", "name": "Rafa Linden", "department": "HR", "email": "rafa.linden@example.com", "role": "Analista", "vip": True},
    {"id": "EMP015", "name": "Nina Harrow", "department": "Facilities", "email": "nina.harrow@example.com", "role": "Coordenador", "vip": False},
    {"id": "EMP016", "name": "Otto Gale", "department": "Security", "email": "otto.gale@example.com", "role": "Gerente", "vip": False},
    {"id": "EMP017", "name": "Luma Frost", "department": "Legal", "email": "luma.frost@example.com", "role": "Diretor", "vip": True},
    {"id": "EMP018", "name": "Gael Thorne", "department": "Sales", "email": "gael.thorne@example.com", "role": "Analista Senior", "vip": False},
    {"id": "EMP019", "name": "Vera Bloom", "department": "Operations", "email": "vera.bloom@example.com", "role": "Assistente", "vip": False},
    {"id": "EMP020", "name": "Noah Sable", "department": "R&D", "email": "noah.sable@example.com", "role": "Desenvolvedor", "vip": False},
]


def seed_data() -> None:
    db = SessionLocal()
    try:
        employee_exists = db.execute(select(Employee.id).limit(1)).scalar_one_or_none()
        team_exists = db.execute(select(Team.category).limit(1)).scalar_one_or_none()

        if not employee_exists:
            db.add_all(Employee(**employee_data) for employee_data in EMPLOYEES)
            logger.info("Seeded %s employees", len(EMPLOYEES))

        if not team_exists:
            db.add_all(
                Team(
                    category=team_data["category"],
                    team_name=team_data["team"],
                    email=team_data["email"],
                    queue=team_data["queue"],
                    sla_default_hours=team_data["sla_default_hours"],
                )
                for team_data in TEAMS.values()
            )
            logger.info("Seeded %s teams", len(TEAMS))

        if not employee_exists or not team_exists:
            db.commit()
        else:
            logger.info("Seed data already present; skipping")
    except Exception:
        db.rollback()
        logger.exception("Failed to seed database")
        raise
    finally:
        db.close()
