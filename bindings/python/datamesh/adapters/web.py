from __future__ import annotations

import urllib.request
from typing import Any

USER_AGENT = "datamesh-sdk/0.2 (Python)"


def safe_urlopen(req: Any, timeout: int = 2) -> Any:
    """``urlopen`` that tolerates the legacy no-timeout signature (TypeError)."""
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except TypeError:
        return urllib.request.urlopen(req)


def fetch_text(url: str, timeout: int = 2, user_agent: str = USER_AGENT) -> str:
    """Reads text from a ``file://`` path, an http(s) URL, or a local path."""
    if url.startswith("file://"):
        with open(url[7:], "r", encoding="utf-8") as f:
            return f.read()
    if url.startswith(("http://", "https://")):
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with safe_urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    with open(url, "r", encoding="utf-8") as f:
        return f.read()
