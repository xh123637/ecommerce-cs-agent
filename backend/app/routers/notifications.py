"""In-app notification endpoints."""

from fastapi import APIRouter, Depends

from .. import repository
from ..auth import get_current_user
from ..schemas import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def notifications(user: dict = Depends(get_current_user)):
    return repository.list_notifications(user)


@router.get("/unread-count")
def unread_count(user: dict = Depends(get_current_user)):
    return {"count": repository.unread_notification_count(user)}


@router.post("/{notification_id}/read")
def read_notification(notification_id: int, user: dict = Depends(get_current_user)):
    repository.mark_notification_read(notification_id, user)
    return {"ok": True}


@router.post("/read-all")
def read_all(user: dict = Depends(get_current_user)):
    return {"updated": repository.mark_all_notifications_read(user)}
