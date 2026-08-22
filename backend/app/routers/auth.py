"""Authentication endpoints."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from .. import repository
from ..auth import (
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..config import WECHAT_APPID, WECHAT_SECRET
from ..schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    WechatLoginRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest):
    user = repository.create_user(
        username=body.username,
        password_hash=hash_password(body.password),
        role="customer",
        display_name=body.display_name or body.username,
    )
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "用户名已存在")
    token = create_token(user["id"], user["role"])
    return {"access_token": token, "user": user}


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = repository.get_user_by_username(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    public = {key: user[key] for key in ("id", "username", "role", "display_name")}
    token = create_token(user["id"], user["role"])
    return {"access_token": token, "user": public}


@router.post("/wechat/login", response_model=TokenResponse)
def wechat_login(body: WechatLoginRequest):
    openid = None
    if WECHAT_APPID and WECHAT_SECRET:
        response = httpx.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": WECHAT_APPID,
                "secret": WECHAT_SECRET,
                "js_code": body.code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        data = response.json()
        openid = data.get("openid")
        if not openid:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "微信登录失败")
    else:
        # 开发模式：未配置微信参数时用 code 作为 openid，方便本地联调。
        openid = f"dev_{body.code}"

    user = repository.get_user_by_openid(openid) or repository.create_wechat_user(openid)
    token = create_token(user["id"], user["role"])
    return {"access_token": token, "user": user}


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return user
