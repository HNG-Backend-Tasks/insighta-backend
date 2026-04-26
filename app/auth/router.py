from fastapi import APIRouter, Depends
from .dependencies import get_current_user, require_admin
from ..models import User

auth_router = APIRouter()


@auth_router.get("/auth/test/user")
def test_user_endpoint(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "role": user.role}


@auth_router.get("/auth/test/admin")
def test_admin_endpoint(user: User = Depends(require_admin)):
    return {"user_id": user.id, "role": user.role}
