from fastapi import APIRouter

from . import group01, group02, group03, group04, group05, group06
from . import group07, group08, group09, group10, group11, group12
from . import platform


router = APIRouter()
router.include_router(platform.router)

for _group_router in (
    group01,
    group02,
    group03,
    group04,
    group05,
    group06,
    group07,
    group08,
    group09,
    group10,
    group11,
    group12,
):
    router.include_router(_group_router.router)
