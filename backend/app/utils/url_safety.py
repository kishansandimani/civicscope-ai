"""SSRF protection. Every outbound fetch of a user-supplied URL (and every redirect hop) goes through here."""
import ipaddress
import socket
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

MAX_URL_LENGTH = 2048
ALLOWED_PORTS = {None, 80, 443}
BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal", "metadata", "instance-data"}


class UnsafeURL(ValueError):
    """Raised when a URL must not be fetched. The message is safe to show to users."""


def _ip_is_public(ip: ipaddress._BaseAddress) -> bool:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _ip_is_public(mapped)
    return ip.is_global and not ip.is_multicast


def _default_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({i[4][0] for i in infos})


def validate_public_url(url: str, resolver: Callable[[str, int], list[str]] | None = None) -> str:
    """Return a normalised URL if it is safe to fetch, otherwise raise UnsafeURL."""
    if not isinstance(url, str) or not url.strip():
        raise UnsafeURL("Enter a website address.")
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise UnsafeURL("That address is too long.")
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeURL("Only http:// and https:// addresses are supported.")
    if parts.username or parts.password:
        raise UnsafeURL("Addresses containing a username or password are not allowed.")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeURL("That address has no website name.")
    try:
        port = parts.port
    except ValueError:
        raise UnsafeURL("That address has an invalid port.")
    if port not in ALLOWED_PORTS:
        raise UnsafeURL("Only standard web ports (80, 443) are allowed.")
    if host in BLOCKED_HOSTNAMES or host.endswith((".local", ".internal", ".localhost")):
        raise UnsafeURL("That address points to a private network and cannot be analysed.")

    try:  # literal IP in the URL
        literal = ipaddress.ip_address(host)
        addresses = [str(literal)]
    except ValueError:
        try:
            addresses = (resolver or _default_resolver)(host, port or (443 if parts.scheme == "https" else 80))
        except (socket.gaierror, UnicodeError, OSError):
            raise UnsafeURL("That website name could not be found.")
    if not addresses:
        raise UnsafeURL("That website name could not be found.")
    for a in addresses:
        if not _ip_is_public(ipaddress.ip_address(a)):
            raise UnsafeURL("That address points to a private network and cannot be analysed.")
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", parts.query, ""))
