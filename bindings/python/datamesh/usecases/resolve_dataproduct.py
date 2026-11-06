from __future__ import annotations

import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from datamesh.adapters.go_bridge import GoCoreBridge
from datamesh.adapters.web import fetch_text

try:
    import yaml
except ImportError:
    yaml = None

_OJS_BLOCK_RE = re.compile(r"```ojs\b.*?```\s*", re.DOTALL)


def strip_ojs_blocks(markdown: str) -> str:
    """Removes Observable JS (```ojs ... ```) visualization blocks from Markdown text."""
    if not markdown:
        return ""
    return _OJS_BLOCK_RE.sub("", markdown).strip()


def _escape_md_pipe(val: Any) -> str:
    s = str(val or "").replace("\r\n", " ").replace("\n", " ").strip()
    return s.replace("|", "\\|")


def _infer_dataset_slug(uri_or_path: str, fallback_title: str = "") -> str:
    clean = (uri_or_path or "").strip().rstrip("/")
    for suffix in ("/index.md", "\\index.md"):
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)]
            break
    if any(clean.endswith(ext) for ext in (".md", ".yaml", ".yml", ".json")):
        parent = os.path.dirname(clean)
        base = os.path.basename(clean)
        if base.startswith("datapackage.") or base == "index.md":
            clean = parent
    for sep in ("/", "\\", ":"):
        if sep in clean:
            slug = clean.rsplit(sep, 1)[-1].strip()
            if slug.endswith(".md"):
                slug = slug[:-3]
            if slug and slug not in ("nodes", "bundles"):
                return slug
    if clean:
        return clean[:-3] if clean.endswith(".md") else clean
    return re.sub(r"[^a-z0-9_\-]+", "_", (fallback_title or "dataset").lower()).strip("_")


def synthesize_contract_markdown(
    dp: Dict[str, Any],
    raw_openapis: Optional[Dict[str, str]] = None,
) -> str:
    """Synthesizes attached DataPackage, OpenAPI, and OWL-CLI contracts into a Markdown section."""
    if not isinstance(dp, dict):
        return ""

    manifest = dp.get("manifest") or {}
    resources = dp.get("resources") or []
    ds_slug = _infer_dataset_slug(str(dp.get("id", "")), str(manifest.get("title", "")))

    sem_field_map: Dict[str, Dict[str, Any]] = {}
    for sf in manifest.get("semantic_fields") or []:
        if isinstance(sf, dict) and sf.get("field_name"):
            sem_field_map[str(sf["field_name"]).lower().strip()] = sf

    sections: List[str] = []

    # 1. Tabular DataPackage Resources & Fields
    if resources:
        res_blocks: List[str] = []
        for res in resources:
            if not isinstance(res, dict):
                continue
            r_name = str(res.get("name", "resource"))
            r_path = str(res.get("path", ""))
            r_fmt = str(res.get("format", "")) or Path(r_path).suffix.lstrip(".")
            triad = f"{ds_slug}:{r_name}"
            lines = [
                f"### Recurso: `{triad}` (`{r_fmt}`)",
                f'- **Tríada SQL**: `"{triad}"`',
            ]
            if r_path:
                lines.append(f"- **Ruta Física**: `{r_path}`")
            lines.append(f'- **Consulta Rápida**: `SELECT * FROM "{triad}" LIMIT 10`')

            fields = res.get("fields") or (res.get("schema") or {}).get("fields") or []
            if fields:
                lines.append("")
                lines.append("| Columna | Tipo | Etiqueta / Descripción | Concepto Semántico (SKOS / OWL) | Valores / Categorías |")
                lines.append("| :--- | :--- | :--- | :--- | :--- |")
                for f in fields:
                    if not isinstance(f, dict):
                        continue
                    f_name = str(f.get("name", ""))
                    f_type = str(f.get("type") or "string")
                    f_title = str(f.get("title") or "").strip()
                    f_desc = str(f.get("description") or "").strip()
                    if f_title and f_desc and f_desc != f_title:
                        label_desc = f"{f_title} — {f_desc}"
                    else:
                        label_desc = f_title or f_desc or "—"

                    concept = str(f.get("concept") or f.get("rdfType") or "").strip()
                    if not concept and f_name.lower() in sem_field_map:
                        concept = str(sem_field_map[f_name.lower()].get("concept_ref") or "").strip()
                    if not concept:
                        concept = "—"

                    cats = f.get("categories") or []
                    if isinstance(cats, list) and cats:
                        shown = [f"`{c}`" for c in cats[:8]]
                        cats_str = ", ".join(shown) + (", ..." if len(cats) > 8 else "")
                    elif isinstance(cats, dict) and cats:
                        shown = [f"`{k}`" for k in list(cats.keys())[:8]]
                        cats_str = ", ".join(shown) + (", ..." if len(cats) > 8 else "")
                    else:
                        cats_str = "—"

                    lines.append(
                        f"| `{_escape_md_pipe(f_name)}` | `{_escape_md_pipe(f_type)}` | "
                        f"{_escape_md_pipe(label_desc)} | {_escape_md_pipe(concept)} | {_escape_md_pipe(cats_str)} |"
                    )
            res_blocks.append("\n".join(lines))
        if res_blocks:
            sections.append("\n\n".join(res_blocks))

    # 2. OpenAPI Service Contracts
    if raw_openapis and yaml is not None:
        for src_path in sorted(raw_openapis.keys()):
            oa_md = _synthesize_openapi_markdown(src_path, raw_openapis[src_path])
            if oa_md:
                sections.append(oa_md)

    # 3. OWL-CLI / OKF-CLI Local Tool Contracts
    for c in manifest.get("contracts") or []:
        if not isinstance(c, dict):
            continue
        c_type = str(c.get("type") or "").lower().strip()
        if c_type in ("owl-cli", "okf-cli") or c.get("binary"):
            cli_md = _synthesize_cli_markdown(c)
            if cli_md:
                sections.append(cli_md)

    if not sections:
        return ""
    return "## Contrato de Datos y Esquema Semántico (Sintetizado)\n\n" + "\n\n".join(sections)


def _synthesize_openapi_markdown(source_path: str, raw_text: str) -> str:
    if yaml is None or not raw_text:
        return ""
    try:
        doc = yaml.safe_load(raw_text)
    except Exception:
        return ""
    if not isinstance(doc, dict):
        return ""
    paths = doc.get("paths") or {}
    info = doc.get("info") or {}
    if not paths and not info.get("title"):
        return ""

    title = str(info.get("title") or os.path.basename(source_path)).strip()
    lines = [f"### Servicio Remoto (OpenAPI): {title}"]
    servers = doc.get("servers") or []
    if servers and isinstance(servers[0], dict) and servers[0].get("url"):
        lines.append(f"- **Servidor Base**: `{servers[0]['url']}`")

    for path_str in sorted(paths.keys()):
        methods = paths[path_str]
        if not isinstance(methods, dict):
            continue
        for method in sorted(methods.keys()):
            op = methods[method]
            if not isinstance(op, dict):
                continue
            upper_m = str(method).upper()
            summary = str(op.get("summary") or op.get("description") or "").strip()
            lines.append("")
            if summary:
                lines.append(f"#### Endpoint: `{upper_m} {path_str}` — {summary}")
            else:
                lines.append(f"#### Endpoint: `{upper_m} {path_str}`")

            params = op.get("parameters") or []
            if params:
                lines.append("")
                lines.append("| Parámetro (Input) | Ubicación | Tipo | Requerido | Concepto Semántico (`x-okf-concept`) | Descripción |")
                lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
                for p in params:
                    if not isinstance(p, dict):
                        continue
                    schema = p.get("schema") or {}
                    p_type = str(schema.get("type") or "string")
                    req_str = "Sí" if p.get("required") else "No"
                    concept = str(p.get("x-okf-concept") or schema.get("x-okf-concept") or "—").strip()
                    desc = str(p.get("description") or "—").strip()
                    lines.append(
                        f"| `{_escape_md_pipe(p.get('name', ''))}` | `{_escape_md_pipe(p.get('in', 'query'))}` | "
                        f"`{_escape_md_pipe(p_type)}` | {req_str} | {_escape_md_pipe(concept)} | {_escape_md_pipe(desc)} |"
                    )

            responses = op.get("responses") or {}
            for status, resp in responses.items():
                if not isinstance(resp, dict):
                    continue
                content = resp.get("content") or {}
                for media in content.values():
                    if not isinstance(media, dict):
                        continue
                    props = ((media.get("schema") or {}).get("properties")) or {}
                    if props:
                        lines.append("")
                        lines.append(f"**Campos de Respuesta (`HTTP {status}`):**")
                        lines.append("")
                        lines.append("| Propiedad (Output) | Tipo | Concepto Semántico (`x-okf-concept`) | Descripción |")
                        lines.append("| :--- | :--- | :--- | :--- |")
                        for pn in sorted(props.keys()):
                            prop = props[pn] or {}
                            p_type = str(prop.get("type") or "any")
                            concept = str(prop.get("x-okf-concept") or "—").strip()
                            desc = str(prop.get("description") or "—").strip()
                            lines.append(
                                f"| `{_escape_md_pipe(pn)}` | `{_escape_md_pipe(p_type)}` | "
                                f"{_escape_md_pipe(concept)} | {_escape_md_pipe(desc)} |"
                            )
    return "\n".join(lines).strip()


def _synthesize_cli_markdown(c: Dict[str, Any]) -> str:
    cmd_name = str(c.get("binary") or "").strip()
    sub = str(c.get("subcommand") or "").strip()
    if sub:
        cmd_name = f"{cmd_name} {sub}".strip()
    if not cmd_name:
        cmd_name = "cli-tool"
    c_type = str(c.get("type") or "owl-cli")
    lines = [f"### Herramienta CLI Local (`{c_type}`): `{cmd_name}`"]

    inputs = c.get("inputs") or []
    cmd_parts = [cmd_name]
    for inp in inputs:
        if isinstance(inp, dict):
            if inp.get("flag"):
                cmd_parts.append(f"{inp['flag']} <{inp.get('name', 'val')}>")
            else:
                cmd_parts.append(f"<{inp.get('name', 'val')}>")
    lines.append(f"- **Plantilla de Ejecución**: `{' '.join(cmd_parts)}`")

    if inputs:
        lines.append("")
        lines.append("| Parámetro (Input) | Flag / Posición | Tipo | Requerido | Concepto Semántico (SKOS / OWL) | Descripción |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for inp in inputs:
            if not isinstance(inp, dict):
                continue
            flag_pos = str(inp.get("flag") or (f"pos #{inp['position']}" if inp.get("position") else "—"))
            p_type = str(inp.get("type") or "string")
            req_str = "Sí" if inp.get("required") else "No"
            concept = str(inp.get("concept") or "—").strip()
            desc = str(inp.get("description") or "—").strip()
            lines.append(
                f"| `{_escape_md_pipe(inp.get('name', ''))}` | `{_escape_md_pipe(flag_pos)}` | "
                f"`{_escape_md_pipe(p_type)}` | {req_str} | {_escape_md_pipe(concept)} | {_escape_md_pipe(desc)} |"
            )

    outputs = c.get("outputs")
    if isinstance(outputs, dict) and (outputs.get("format") or outputs.get("concept") or outputs.get("description")):
        out_fmt = str(outputs.get("format") or "stdout")
        out_concept = str(outputs.get("concept") or "—")
        out_line = f"\n- **Salida Semántica (Output)**: Formato `{out_fmt}` | Concepto: `{out_concept}`"
        if outputs.get("description"):
            out_line += f" — {outputs['description']}"
        lines.append(out_line)

    return "\n".join(lines).strip()


class ResolveDataProductUseCase:
    """Resolves an ODKF node document and returns its DataProduct metadata with synthesized Markdown contracts."""

    def __init__(
        self,
        bridge: GoCoreBridge,
        catalog_discovery_fn: Optional[Callable[[Optional[str]], Dict[str, Any]]] = None,
    ):
        self._bridge = bridge
        self._catalog_discovery_fn = catalog_discovery_fn

    def _resolve_slug_or_triad_uri(self, uri: str) -> str:
        clean = (uri or "").strip()
        if not clean or clean.startswith(("http://", "https://", "file://")) or os.path.exists(clean):
            return clean

        from datamesh.constants import get_cache_dir, get_datamesh_home

        normalized = clean.replace(":", "/")
        candidate_roots = [
            Path("knowledge/nodes"),
            Path("bundles"),
            Path("examples/bundles"),
            Path("../bundles"),
            Path("../catalogo-datamesh/knowledge/nodes"),
            get_cache_dir() / "nodes",
            get_datamesh_home() / "knowledge" / "nodes",
        ]
        for root in candidate_roots:
            cand = root / normalized
            if cand.exists():
                if cand.is_dir() and (cand / "index.md").exists():
                    return str(cand / "index.md")
                return str(cand)
            cand_idx = root / normalized / "index.md"
            if cand_idx.exists():
                return str(cand_idx)

        if self._catalog_discovery_fn is not None:
            try:
                cat = self._catalog_discovery_fn(None)
                parts = normalized.split("/", 1)
                slug = parts[0].lower().strip()
                subpath = parts[1] if len(parts) > 1 else ""
                for entry in cat.get("entries", []):
                    u = str(entry.get("uri", "")).lower()
                    r_url = str(entry.get("resolved_url", ""))
                    t = str(entry.get("title", "")).lower()
                    if (
                        f"/{slug}/" in u
                        or u.endswith(f"/{slug}")
                        or f"/{slug}/" in r_url.lower()
                        or t == slug
                    ):
                        if subpath:
                            base_r = r_url[:-9] if r_url.endswith("/index.md") else r_url.rstrip("/")
                            return f"{base_r}/{subpath}"
                        return r_url

                src_url = str(cat.get("source_url") or "")
                if src_url.startswith(("http://", "https://")):
                    origin = src_url.split("/llms")[0].rstrip("/")
                    if normalized.endswith(".md"):
                        return f"{origin}/raw/nodes/{normalized}"
                    return f"{origin}/raw/nodes/{normalized}/index.md"
            except Exception:
                pass

        return clean

    def execute(self, uri: str) -> Dict[str, Any]:
        actual_uri = self._resolve_slug_or_triad_uri(uri)

        go_result = self._bridge.call("DataMeshResolveDataProduct", actual_uri)
        if go_result and isinstance(go_result, dict):
            manifest = go_result.get("manifest") or {}
            if not go_result.get("title") and manifest.get("title"):
                go_result["title"] = manifest["title"]
            return go_result

        content = fetch_text(actual_uri, timeout=5)
        raw_content = content

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError("No YAML frontmatter found in node markdown")

        frontmatter = parts[1]
        body = strip_ojs_blocks(parts[2].strip())

        manifest: Dict[str, Any] = {"dimensions": [], "contracts": []}
        try:
            parsed_yaml = yaml.safe_load(frontmatter) if yaml is not None else None
            if isinstance(parsed_yaml, dict):
                manifest.update(parsed_yaml)
                if "dimensions" not in manifest or not manifest["dimensions"]:
                    dom = parsed_yaml.get("domain") or parsed_yaml.get("dominio")
                    manifest["dimensions"] = [dom] if dom else ["core"]
                if "contracts" not in manifest:
                    manifest["contracts"] = []
                if "title" not in manifest and "id" in parsed_yaml:
                    manifest["title"] = str(parsed_yaml["id"])
        except Exception:
            for line in frontmatter.splitlines():
                line_str = line.strip()
                if not line_str or line_str.startswith("#"):
                    continue
                if line_str.startswith("title:"):
                    manifest["title"] = line_str.split(":", 1)[1].strip().strip("\"'")
                elif line_str.startswith("type:"):
                    manifest["type"] = line_str.split(":", 1)[1].strip().strip("\"'")
                elif line_str.startswith("id:") and "title" not in manifest:
                    manifest["title"] = line_str.split(":", 1)[1].strip().strip("\"'")
                elif line_str.startswith("- ") and "dimensions" in manifest:
                    manifest["dimensions"].append(line_str[2:].strip().strip("\"'"))

            if not manifest["dimensions"]:
                manifest["dimensions"] = ["core"]

        # Discover attached DataPackage or OpenAPI contracts in Python fallback
        is_specific_md = actual_uri.lower().endswith(".md") and not actual_uri.lower().endswith("/index.md") and os.path.basename(actual_uri.lower()) != "index.md"
        base_dir = actual_uri.rsplit("/", 1)[0] if "/" in actual_uri else "."
        resources: List[Dict[str, Any]] = []
        raw_openapis: Dict[str, str] = {}

        def _resolve_ref(ref_str: str) -> str:
            ref_clean = ref_str.strip()
            if ref_clean.startswith(("http://", "https://", "file://")):
                return ref_clean
            if actual_uri.startswith(("http://", "https://")):
                return urllib.parse.urljoin(base_dir.rstrip("/") + "/", ref_clean.lstrip("./"))
            return str(Path(base_dir) / ref_clean.lstrip("./"))

        candidate_dp_files: List[str] = []
        for c in manifest.get("contracts") or []:
            if not isinstance(c, dict):
                continue
            ref_p = str(c.get("path") or c.get("ref") or "").strip()
            if not ref_p:
                continue
            full_p = _resolve_ref(ref_p)
            c_type = str(c.get("type") or "").lower()
            if c_type == "openapi" or "openapi." in full_p.lower() or "swagger." in full_p.lower():
                try:
                    raw_openapis[full_p] = fetch_text(full_p, timeout=3)
                except Exception:
                    pass
            else:
                candidate_dp_files.append(full_p)

        if not is_specific_md:
            for std_name in ("datapackage.yaml", "datapackage.yml", "datapackage.json"):
                candidate_dp_files.append(_resolve_ref(std_name))

            for dp_path in candidate_dp_files:
                try:
                    dp_text = fetch_text(dp_path, timeout=3)
                    parsed_dp = (
                        json.loads(dp_text)
                        if dp_path.endswith(".json")
                        else (yaml.safe_load(dp_text) if yaml else None)
                    )
                    if isinstance(parsed_dp, dict) and isinstance(parsed_dp.get("resources"), list):
                        for r in parsed_dp["resources"]:
                            if not isinstance(r, dict) or not r.get("name"):
                                continue
                            r_path = str(r.get("path") or "")
                            if not r_path and isinstance(r.get("url"), str):
                                r_path = r["url"]
                            fields = (r.get("schema") or {}).get("fields") or r.get("fields") or []
                            resources.append({
                                "name": r["name"],
                                "path": _resolve_ref(r_path) if r_path else "",
                                "format": r.get("format") or Path(r_path).suffix.lstrip("."),
                                "description": r.get("description", ""),
                                "fields": fields,
                            })
                        break
                except Exception:
                    pass

        dp_dict: Dict[str, Any] = {
            "id": actual_uri,
            "title": manifest.get("title", ""),
            "manifest": manifest,
            "description": body,
            "resources": resources,
            "raw_content": raw_content,
        }

        synth_md = synthesize_contract_markdown(dp_dict, raw_openapis=raw_openapis)
        if synth_md and "## Contrato de Datos y Esquema Semántico" not in dp_dict["description"]:
            if dp_dict["description"]:
                dp_dict["description"] = dp_dict["description"] + "\n\n" + synth_md
            else:
                dp_dict["description"] = synth_md

        return dp_dict
