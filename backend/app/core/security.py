"""FastAPI dependency: the signed-in user for a request."""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.tokens import TokenError, verify_token

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    email: str | None
    token: str


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.")
    s = get_settings()
    try:
        v = verify_token(creds.credentials, jwt_secret=s.supabase_jwt_secret, supabase_url=s.supabase_url, anon_key=s.supabase_anon_key)
    except TokenError as e:
        raise HTTPException(e.status_code, e.message)
    return CurrentUser(id=v.id, email=v.email, token=creds.credentials)
