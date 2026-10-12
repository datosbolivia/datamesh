from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, List

from datamesh.adapters.web import fetch_text


def parse_llms_txt(content: str, source_url: str) -> Dict[str, Any]:
    """Parses an llms.txt catalog document into a normalized entries structure.

    Supports both the flat ``- [title](uri): desc`` format and the hierarchical
    ODKF requirement/bullet format (``### [REQ-01] ...`` plus ``* [ID] ... : /raw``).
    """
    entries: List[Dict[str, Any]] = []
    entry_pattern = re.compile(r"^-\s*\[(.*?)\]\((.*?)\)(?::\s*(.*))?$")
    domain_pattern = re.compile(r"\(Dominio:\s*([^)]*?)(?:\.|\)|Recursos:)")
    rec_pattern = re.compile(r"Recursos:\s*([^)]+)\)")

    req_header_pattern = re.compile(r"^###\s*\[(.*?)\]\s*(.*?)(?:\s*\((?:Institución|Agencia):\s*([^)]+)\))?$")
    triad_pattern = re.compile(r"Tríada:\s*`([^`]+)`")
    bullet_item_pattern = re.compile(r"^\s*[*+-]\s*\[(.*?)\]\s*(.*)")
    raw_spec_pattern = re.compile(r"^-\s*Especificación Técnica:\s*(\S+)")

    title = ""
    description = ""
    current_req = None

    for line in content.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        if line_str.startswith("# ") and not title:
            title = line_str[2:].strip()
            continue
        if line_str.startswith("> ") and not description:
            description = line_str[2:].strip()
            continue

        # 1. Section Header: ### [REQ-01] Title (Institución: ...)
        rm = req_header_pattern.match(line_str)
        if rm:
            current_req = {
                "id": rm.group(1).strip(),
                "title": rm.group(2).strip(),
                "institution": rm.group(3) or "",
                "domain": "",
                "spec_uri": "",
            }
            continue

        if current_req:
            if line_str.startswith("- Dominio Temático:"):
                current_req["domain"] = line_str.split(":", 1)[1].strip()
                continue
            sm = raw_spec_pattern.match(line_str)
            if sm:
                current_req["spec_uri"] = sm.group(1).strip()
                continue

            # Hierarchical bullet: * [REQ_01_A] Title (Tríada: `...`, ...): /raw/path.md
            if (line_str.startswith("* [") or line_str.startswith("- [")) and ":" in line_str:
                last_colon = line_str.rfind(":")
                comp_uri = line_str[last_colon + 1:].strip()
                if comp_uri.startswith("/") or comp_uri.startswith("http://") or comp_uri.startswith("https://") or comp_uri.endswith(".md"):
                    prefix = line_str[:last_colon].strip()
                    bm = bullet_item_pattern.match(prefix)
                    if bm:
                        comp_id = bm.group(1).strip()
                        rest = bm.group(2).strip()
                        tm = triad_pattern.search(rest)
                        triad = tm.group(1) if tm else ""

                        if "(Tríada:" in rest:
                            title_clean, meta_clean = rest.split("(Tríada:", 1)
                            title_clean = title_clean.strip()
                            meta_clean = "Tríada:" + meta_clean.rstrip(")")
                        elif "(Dominio:" in rest:
                            title_clean, meta_clean = rest.split("(Dominio:", 1)
                            title_clean = title_clean.strip()
                            meta_clean = "Dominio:" + meta_clean.rstrip(")")
                        else:
                            title_clean = rest
                            meta_clean = ""

                        resolved = urllib.parse.urljoin(source_url, comp_uri)
                        req_id = current_req["id"]
                        full_title = f"[{req_id}] {title_clean}"
                        req_t = current_req.get("title", "")
                        desc = f"{title_clean} ({req_t}). {meta_clean}".strip()
                        entries.append({
                            "title": full_title,
                            "uri": comp_uri,
                            "resolved_url": resolved,
                            "description": desc,
                            "domain": current_req.get("domain", ""),
                            "triad": triad,
                            "resources": [comp_id.lower()],
                            "catalog_source": source_url,
                        })
                        continue

        # 2. Standard Flat llms.txt entry
        m = entry_pattern.match(line_str)
        if m:
            item_title, raw_uri, desc = m.group(1), m.group(2), m.group(3) or ""
            resolved = urllib.parse.urljoin(source_url, raw_uri)
            dm = domain_pattern.search(desc)
            domain = dm.group(1).strip() if dm else ""

            rm_match = rec_pattern.search(desc)
            recs = [r.strip() for r in rm_match.group(1).split(",")] if rm_match else []
            clean_desc = desc.split("(Dominio:")[0].strip()

            entries.append({
                "title": item_title,
                "uri": raw_uri,
                "resolved_url": resolved,
                "description": clean_desc,
                "domain": domain,
                "resources": recs,
                "catalog_source": source_url,
            })

    return {
        "title": title or "Sovereign Catalog",
        "description": description,
        "source_url": source_url,
        "entries": entries,
    }


class LLMSTxtCatalogFetcher:
    """Fetches and parses a single llms.txt catalog (file:// or http(s))."""

    def fetch(self, url: str) -> Dict[str, Any]:
        return parse_llms_txt(fetch_text(url, timeout=2), url)
