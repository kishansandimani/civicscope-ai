"""Supabase access.

- admin(): service-role client, server-side only (bypasses RLS). Every query made
  with it MUST filter by the authenticated user's id explicitly.
- for_user(token): anon-key client carrying the user's JWT so Postgres RLS applies.
"""
from functools import lru_cache
from supabase import Client, create_client
try:
    from supabase.lib.client_options import ClientOptions
except ImportError:  # newer supabase-py
    from supabase.lib.client_options import SyncClientOptions as ClientOptions

from app.core.config import get_settings


class SupabaseNotConfigured(RuntimeError):
    pass


def _require():
    s = get_settings()
    if not s.supabase_configured:
        raise SupabaseNotConfigured("Supabase environment variables are not set.")
    return s


@lru_cache
def admin() -> Client:
    s = _require()
    return create_client(s.supabase_url, s.supabase_service_role_key)


def for_user(access_token: str) -> Client:
    s = _require()
    client = create_client(s.supabase_url, s.supabase_anon_key,
                           options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"}))
    client.postgrest.auth(access_token)
    return client


def anon() -> Client:
    s = _require()
    return create_client(s.supabase_url, s.supabase_anon_key)
