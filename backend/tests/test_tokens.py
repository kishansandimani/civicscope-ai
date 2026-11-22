import time
import jwt
from app.core import tokens
from app.core.tokens import TokenError, verify_token

SECRET = "x" * 40


def make(sub="u1", exp=3600, aud="authenticated", secret=SECRET):
    return jwt.encode({"sub": sub, "email": "a@b.in", "aud": aud, "exp": int(time.time()) + exp}, secret, algorithm="HS256")


def fail(fn):
    try:
        fn()
    except TokenError as e:
        return e.status_code
    raise AssertionError("expected TokenError")


def _reset():
    tokens._cache.clear()


def test_local_hs256_fast_path_and_cache():
    _reset()
    calls = []
    t = make()
    v = verify_token(t, jwt_secret=SECRET, fetcher=lambda *a: calls.append(a) or {})
    assert (v.id, v.email) == ("u1", "a@b.in") and not calls          # no remote call needed
    assert verify_token(t, jwt_secret=SECRET).id == "u1"               # served from cache


def test_expired_and_bad_audience_rejected():
    _reset()
    assert fail(lambda: verify_token(make(exp=-10), jwt_secret=SECRET)) == 401
    # wrong audience / wrong secret falls through to the remote check, which must also reject
    def reject(*a): raise TokenError(401, "nope")
    assert fail(lambda: verify_token(make(aud="other"), jwt_secret=SECRET, supabase_url="http://s", anon_key="k", fetcher=reject)) == 401
    assert fail(lambda: verify_token(make(secret="y" * 40), jwt_secret=SECRET, supabase_url="http://s", anon_key="k", fetcher=reject)) == 401


def test_remote_path_for_asymmetric_key_projects():
    _reset()
    seen = []
    def remote(tok, url, key): seen.append((url, key)); return {"id": "u9", "email": "z@z.in"}
    t = "not-a-jwt-we-can-verify-locally"
    v = verify_token(t, jwt_secret="", supabase_url="https://p.supabase.co", anon_key="anon", fetcher=remote)
    assert v.id == "u9" and seen == [("https://p.supabase.co", "anon")]
    verify_token(t, supabase_url="https://p.supabase.co", anon_key="anon", fetcher=remote)
    assert len(seen) == 1                                              # cached for 60 s


def test_cache_expires():
    _reset()
    clock = [1000.0]
    n = []
    def remote(*a): n.append(1); return {"id": "u2"}
    kw = dict(supabase_url="http://s", anon_key="k", fetcher=remote, now=lambda: clock[0])
    verify_token("tok", **kw); verify_token("tok", **kw); assert len(n) == 1
    clock[0] += tokens.CACHE_SECONDS + 1
    verify_token("tok", **kw); assert len(n) == 2


def test_unconfigured_and_missing_id():
    _reset()
    assert fail(lambda: verify_token("tok")) == 503
    assert fail(lambda: verify_token("tok2", supabase_url="http://s", anon_key="k", fetcher=lambda *a: {})) == 401
