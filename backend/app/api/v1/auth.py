from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.security import create_access_token
from app.core.database import mongo_db

router = APIRouter(prefix="/auth", tags=["auth"])

PROVIDERS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "user:email",
    },
}


def _get_client(provider: str):
    if provider == "google":
        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET
    elif provider == "github":
        client_id = settings.GITHUB_CLIENT_ID
        client_secret = settings.GITHUB_CLIENT_SECRET
    else:
        raise ValueError(f"Unknown provider: {provider}")
    if not client_id or not client_secret:
        raise ValueError(f"{provider} OAuth not configured")
    return client_id, client_secret


@router.get("/{provider}")
async def login(provider: str, request: Request):
    if provider not in PROVIDERS:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?error=unknown_provider")
    try:
        client_id, _ = _get_client(provider)
    except ValueError:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?error=oauth_not_configured")

    cfg = PROVIDERS[provider]
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/auth/{provider}/callback"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": cfg["scope"],
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{cfg['authorize_url']}?{query}")


@router.get("/{provider}/callback")
async def callback(provider: str, code: str, request: Request):
    import httpx

    if provider not in PROVIDERS:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?error=unknown_provider")

    cfg = PROVIDERS[provider]
    client_id, client_secret = _get_client(provider)
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/auth/{provider}/callback"

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            cfg["token_url"],
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(url=f"{settings.FRONTEND_URL}?error=token_failed")

        if provider == "google":
            userinfo_resp = await client.get(
                cfg["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo = userinfo_resp.json()
            email = userinfo.get("email", "")
            display_name = userinfo.get("name", "")
            avatar_url = userinfo.get("picture", "")
            provider_id = userinfo.get("sub", "")
        else:
            userinfo_resp = await client.get(
                cfg["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo = userinfo_resp.json()
            email = userinfo.get("email", "") or f"{userinfo.get('login')}@github"
            display_name = userinfo.get("name") or userinfo.get("login", "")
            avatar_url = userinfo.get("avatar_url", "")
            provider_id = str(userinfo.get("id", ""))

    user_doc = await mongo_db.users.find_one_and_update(
        {"auth_provider": provider, "provider_id": provider_id},
        {
            "$set": {
                "email": email,
                "display_name": display_name,
                "avatar_url": avatar_url,
            },
            "$setOnInsert": {
                "auth_provider": provider,
                "provider_id": provider_id,
                "preferred_language": "zh",
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
        return_document=True,
    )

    jwt_token = create_access_token(
        {"sub": str(user_doc["_id"]), "provider": provider}
    )

    response = RedirectResponse(url=settings.FRONTEND_URL)
    response.set_cookie(
        key="token",
        value=jwt_token,
        httponly=True,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        samesite="lax",
    )
    return response


@router.get("/me")
async def get_me(request: Request):
    from app.core.security import decode_access_token

    token = request.cookies.get("token")
    if not token:
        return {"authenticated": False}
    payload = decode_access_token(token)
    if not payload:
        return {"authenticated": False}
    user = await mongo_db.users.find_one({"_id": __import__("bson").ObjectId(payload["sub"])})
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user": {
            "id": str(user["_id"]),
            "email": user["email"],
            "displayName": user["display_name"],
            "avatarUrl": user.get("avatar_url", ""),
            "provider": user["auth_provider"],
        },
    }


@router.post("/logout")
async def logout():
    from fastapi.responses import RedirectResponse

    response = RedirectResponse(url="/")
    response.delete_cookie(key="token")
    return response
