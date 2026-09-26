import importlib

from sqlalchemy.orm import Session


SEEDER_PACKAGE = __name__


def load_seeder(group_id: int):
    module = importlib.import_module(f"{SEEDER_PACKAGE}.group{group_id:02d}")
    return module.seed_group


def seed_group(db: Session, group_id: int) -> None:
    load_seeder(group_id)(db)
