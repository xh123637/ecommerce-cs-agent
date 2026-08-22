"""Staff team routes for supervisors/admins (assignment targets)."""

from fastapi import APIRouter, Depends

from .. import repository
from ..auth import require_supervisor

router = APIRouter(prefix="/api/staff", tags=["staff"])


@router.get("")
def list_staff(user: dict = Depends(require_supervisor)):
    return repository.list_staff_users()
