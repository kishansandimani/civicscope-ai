"""Verify a Supabase access token. Pure logic (no FastAPI / settings imports) so it is unit-testable.

Order: (1) optional fast path, local HS256 check with the project's legacy JWT secret;
       (2) otherwise ask Supabase Auth itself (GET /auth/v1/user), which works for every signing-key type.
Results are cached briefly so a page that fires several API calls does not hit Supabase Auth each time.
"""
import hashlib
import time
from dataclasses import dataclass
from typing import Callable

import jwt

CACHE_SECONDS = 60
_cache: dict[str, tuple[float, "Verified"]] = {}


class TokenError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code, self.message = status_code, message


@dataclass
class Verified:
    id: str
    email: str | None


def _key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def fetch_user_remote(token: str, supabase_url: str, anon_key: str) -> dict:
    import httpx
    try:
        r = httpx.get(f"{supabase_url.rstrip('/')}/auth/v1/user", headers={"apikey": anon_key, "Authorization": f"Bearer {token}"}, timeout=8.0)
    except httpx.HTTPError:
        raise TokenError(503, "Authentication service is unreachable. Please try again.")
    if r.status_code in (401, 403):
        raise TokenError(401, "Session expired or invalid. Please sign in again.")
    if r.status_code != 200:
        raise TokenError(503, "Authentication service error. Please try again.")
    return r.json()


def verify_token(token: str, *, jwt_secret: str = "", supabase_url: str = "", anon_key: str = "",
                 fetcher: Callable[[str, str, str], dict] = fetch_user_remote, now: Callable[[], float] = time.time) -> Verified:
    k = _key(token)
    hit = _cache.get(k)
    if hit and hit[0] > now():
        return hit[1]

    verified: Verified | None = None
    if jwt_secret:
        try:
            claims = jwt.decode(token, jwt_secret, algorithms=["HS256"], audience="authenticated")
            verified = Verified(claims["sub"], claims.get("email"))
        except jwt.ExpiredSignatureError:
            raise TokenError(401, "Session expired. Please sign in again.")
        except (jwt.InvalidAlgorithmError, jwt.InvalidSignatureError, jwt.DecodeError, jwt.InvalidAudienceError, KeyError):
            verified = None        # maybe a project with asymmetric keys: fall through to the remote check
        except jwt.PyJWTError:
            raise TokenError(401, "Invalid authentication token.")
    if verified is None:
        if not (supabase_url and anon_key):
            raise TokenError(503, "Authentication is not configured on the server.")
        u = fetcher(token, supabase_url, anon_key)
        if not u.get("id"):
            raise TokenError(401, "Invalid authentication token.")
        verified = Verified(u["id"], u.get("email"))

    if len(_cache) > 2000:
        _cache.clear()
    _cache[k] = (now() + CACHE_SECONDS, verified)
    return verified
