from __future__ import annotations

import ipaddress
import os
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Set

_TRUTHY = {"1", "true", "yes", "on"}


def _is_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def insecure_tls_enabled() -> bool:
    """Returns True only when the operator explicitly opts into unverified TLS.

    Controlled by the DATAMESH_INSECURE_TLS environment variable. Certificate
    verification is NEVER silently disabled; the insecure fallback is opt-in.
    """
    return _is_true("DATAMESH_INSECURE_TLS")


def _is_certificate_error(err: Exception) -> bool:
    reason = getattr(err, "reason", None)
    return (
        isinstance(reason, ssl.SSLError)
        or "CERTIFICATE_VERIFY_FAILED" in str(err)
        or "certificate" in str(err).lower()
    )


def open_url(req: Any, timeout: int = 30) -> Any:
    """Opens a URL keeping TLS verification on by default.

    On a certificate error the request fails, unless DATAMESH_INSECURE_TLS=1 is
    set, in which case it is retried with an unverified SSL context (MITM risk).
    """
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.URLError as err:
        if not _is_certificate_error(err):
            raise
        if not insecure_tls_enabled():
            target = getattr(req, "full_url", req)
            raise RuntimeError(
                f"TLS certificate verification failed for '{target}'. "
                "Set DATAMESH_INSECURE_TLS=1 only if you explicitly accept the "
                "man-in-the-middle risk (e.g. self-signed government CAs)."
            ) from err
        unverified_ctx = ssl.create_default_context()
        unverified_ctx.check_hostname = False
        unverified_ctx.verify_mode = ssl.CERT_NONE
        return urllib.request.urlopen(req, timeout=timeout, context=unverified_ctx)


def _allowed_hosts() -> Set[str]:
    raw = os.environ.get("DATAMESH_PROXY_ALLOWED_HOSTS", "")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def host_is_allowed(host: str) -> bool:
    """SSRF guard: resolves a host and blocks private/loopback/link-local targets.

    An explicit allowlist (DATAMESH_PROXY_ALLOWED_HOSTS) takes precedence. If no
    allowlist is set, DATAMESH_PROXY_ALLOW_PRIVATE=1 restores the old permissive
    behavior; otherwise private ranges are refused.
    """
    if not host:
        return False
    allowed = _allowed_hosts()
    if allowed:
        return host.lower() in allowed
    if _is_true("DATAMESH_PROXY_ALLOW_PRIVATE"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if _is_blocked_ip(ip):
            return False
    return True


def is_forbidden_local_ref(uri: str) -> bool:
    """True when a caller-supplied reference points at an arbitrary local file.

    Used at the MCP/HTTP boundary to prevent reading local files such as
    '/etc/passwd' or 'file:///etc/secret' as a dataset resource. Remote URLs and
    canonical triads are permitted.
    """
    text = uri.strip()
    if text.startswith(("http://", "https://")):
        return False
    if text.startswith("file://"):
        return True
    if os.path.isabs(text):
        return True
    return ".." in re.split(r"[\\/]", text)


def validate_proxy_url(url: str) -> str:
    """Validates an outbound proxy target: http/https scheme and an allowed host."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http/https URLs are allowed")
    if not parsed.hostname:
        raise ValueError("Target URL must include a host")
    if not host_is_allowed(parsed.hostname):
        raise PermissionError(
            f"Host '{parsed.hostname}' is not allowed by the outbound proxy policy "
            "(private/loopback hosts are blocked; configure DATAMESH_PROXY_ALLOWED_HOSTS to allow)."
        )
    return url
