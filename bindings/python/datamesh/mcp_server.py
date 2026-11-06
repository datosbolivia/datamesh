from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import datamesh as dm
from datamesh.adapters.engine.sql_utils import read_expression
from datamesh.net import is_forbidden_local_ref, validate_proxy_url
from datamesh.usecases.resolve_dataproduct import strip_ojs_blocks

SERVER_NAME = "datamesh-mcp-server"
SERVER_VERSION = "0.2.2"

TOOLS = [
    {
        "name": "datamesh_discover_catalogs",
        "description": "Discovers and lists sovereign open data products across configured federated catalogs or a specified llms.txt URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "catalog_url": {
                    "type": "string",
                    "description": "Optional catalog URL. If omitted, discovers across all configured sovereign catalogs."
                }
            }
        }
    },
    {
        "name": "datamesh_search_catalog",
        "description": "Searches data products across sovereign catalogs by keyword (accent-insensitive, multi-token) matching title, description, domain, URI, or resources.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Search keyword (e.g. 'elecciones', 'creditos', 'aire')."
                },
                "catalog_url": {
                    "type": "string",
                    "description": "Optional catalog URL to scope search to."
                }
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "datamesh_resolve_context",
        "description": "Synthesizes a 4-part Semantic Context Map in Markdown for a domain query or concept: (1) SKOS/OWL Concepts, (2) Static Datasets & SQL Triads, (3) OpenAPI Services & OWL-CLI Tools, and (4) Cross-Dataset Semantic Join suggestions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Concept, entity, or analytical topic to resolve across the Knowledge Graph (e.g. 'municipio', 'reservas', 'creditos', 'calidad del aire')."
                },
                "catalog_url": {
                    "type": "string",
                    "description": "Optional catalog URL to scope discovery."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "datamesh_get_dataproduct",
        "description": "Resolves an OKF v0.2 Data Product manifest and synthesized Markdown contract table (columns, types, SKOS concepts, OpenAPI endpoints, OWL-CLI tools, and SQL triads) from a node URI, URL, or slug.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Data product node URI, slug (e.g. 'bcb-semanal'), or HTTP URL."
                },
                "include_code_blocks": {
                    "type": "boolean",
                    "description": "Optional: set to true to keep raw Observable JS (```ojs) blocks in description (default: false)."
                },
                "insecure": {
                    "type": "boolean",
                    "description": "Optional: set to true to bypass TLS certificate verification."
                }
            },
            "required": ["uri"]
        }
    },
    {
        "name": "datamesh_query_resource",
        "description": "Queries a tabular CSV/TSV data product resource with column equality filters and row limits.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_uri": {
                    "type": "string",
                    "description": "Direct HTTP URL or local file path to the tabular CSV/TSV file."
                },
                "filters": {
                    "type": "object",
                    "description": "Key-value map of column names and filter values (e.g. {'departamento': 'La Paz'}).",
                    "additionalProperties": {"type": "string"}
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return."
                },
                "insecure": {
                    "type": "boolean",
                    "description": "Optional: set to true to bypass TLS certificate verification."
                }
            },
            "required": ["resource_uri"]
        }
    },
    {
        "name": "datamesh_sql_query",
        "description": "Executes full ANSI/DuckDB SQL queries with canonical triad table names 'catalogo:dataset:resource' (e.g. SELECT departamento, SUM(votos_validos) as total FROM \"bolivia:elecciones:votos\" GROUP BY departamento). Seamlessly unifies heterogeneous formats (Parquet, CSV, TSV, JSON) in memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql_query": {
                    "type": "string",
                    "description": "Full ANSI SQL query referencing tables as 'catalogo:dataset:resource'."
                },
                "sql": {
                    "type": "string",
                    "description": "Alternative alias for sql_query."
                },
                "insecure": {
                    "type": "boolean",
                    "description": "Optional: set to true to bypass TLS certificate verification (useful for self-signed or unverified government SSL certificates)."
                }
            },
            "required": ["sql_query"]
        }
    },
    {
        "name": "query_sql",
        "description": "Alias for datamesh_sql_query. Executes DuckDB SQL queries over datasets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Full ANSI SQL query referencing dataset tables."
                },
                "sql_query": {
                    "type": "string",
                    "description": "Full ANSI SQL query."
                },
                "insecure": {
                    "type": "boolean",
                    "description": "Optional: set to true to bypass TLS certificate verification."
                }
            },
            "required": ["sql"]
        }
    },
    {
        "name": "read_resource",
        "description": "Fetches a remote or cached dataset resource bypassing browser CORS restrictions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Resource URI or HTTP URL."
                },
                "insecure": {
                    "type": "boolean",
                    "description": "Optional: set to true to bypass TLS certificate verification."
                }
            },
            "required": ["uri"]
        }
    },
    {
        "name": "datamesh_discover_endpoint",
        "description": "Discovers catalog capabilities and authentication requirements via /.well-known/datamesh.json or active probing (CKAN and OKF/llms.txt).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Target catalog URL or domain (e.g. 'https://datos.gob.bo' or 'https://datosbolivia.github.io')."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "datamesh_harvest_ckan",
        "description": "Harvests open data packages from a CKAN instance and reconstructs OKF v0.2 knowledge bundles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "CKAN portal or API URL."
                },
                "query": {
                    "type": "string",
                    "description": "Optional search filter query."
                },
                "limit": {
                    "type": "integer",
                    "description": "Max packages to harvest (default: 10)."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "datamesh_get_lineage",
        "description": "Inspects dataset provenance, upstream dependencies, and downstream derived datasets in the lineage DAG graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "Dataset identifier, triad, or file path to inspect (optional; if omitted, returns the whole catalog DAG)."
                },
                "catalog_url": {
                    "type": "string",
                    "description": "Optional catalog URL to scope lineage discovery."
                }
            }
        }
    },
    {
        "name": "datamesh_handshake",
        "description": "Performs identity handshake using OpenSSH GitHub DID (did:github:<user>) or Ed25519 digital signature, returning effective policy permissions and constraints (aggregate-only, hidden columns, hashed columns, row filters).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "did": {
                    "type": "string",
                    "description": "DID identity URI (e.g. 'did:github:username')."
                },
                "public_key": {
                    "type": "string",
                    "description": "OpenSSH public key string (e.g. 'ssh-ed25519 AAAAC3... user@host') or 64-char hex key."
                },
                "challenge": {
                    "type": "string",
                    "description": "Challenge string signed by the private key."
                },
                "signature": {
                    "type": "string",
                    "description": "Ed25519 digital signature of challenge in hex format."
                },
                "dataset_policy": {
                    "type": "string",
                    "description": "Optional policy name (e.g. 'zero_microdata') or JSON GranularPolicy to evaluate."
                }
            }
        }
    },
    {
        "name": "datamesh_read_concept_body",
        "description": "Reads the Markdown body, synthesized contract table, and operational documentation of an OKF concept or dataset node (excluding frontmatter and OJS code blocks by default).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Concept/dataset slug (e.g. 'bcb-semanal'), relative path ('air_quality/concepts/air_quality_index.md'), or URL to resolve."
                },
                "include_code_blocks": {
                    "type": "boolean",
                    "description": "Optional: set to true to include raw ```ojs visualization blocks (default: false)."
                }
            },
            "required": ["uri"]
        }
    },
    {
        "name": "datamesh_get_knowledge_graph",
        "description": "Extracts the Unified Semantic Knowledge Graph v2 (nodes: dataset, resource, service, cli_tool, concept; edges: HAS_RESOURCE, MEASURES_CONCEPT, ACCEPTS_CONCEPT, RETURNS_CONCEPT, DERIVED_FROM, SKOS_MATCH) across a sovereign catalog or local workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "catalog_url": {
                    "type": "string",
                    "description": "Optional catalog URL or local bundle directory. If omitted, traverses the configured catalogs and local workspace bundles."
                }
            }
        }
    }
]

GUARDRAILS_INSTRUCTIONS = (
    "DataMesh Sovereign Agent Guardrails:\n"
    "1. STRICT GROUNDEDNESS: You must answer questions using exclusively the data returned by datamesh tools. "
    "Never invent, guess, or extrapolate figures, dates, column names, or table rows.\n"
    "2. MANDATORY CITATION: Always cite the canonical triad 'catalogo:dataset:resource' (e.g. 'air_quality:Compilación de datos de calidad del aire de Bolivia').\n"
    "3. NULL TRANSPARENCY: If a query returns 0 rows or null values, explicitly tell the user that no matching records exist. Do NOT generate mock or speculative answers.\n"
    "4. SCHEMA VERIFICATION: Before complex SQL, verify column names using datamesh_get_dataproduct or LIMIT 1 queries.\n"
    "5. FACT VS HYPOTHESIS: Clearly separate verified database rows from external hypotheses or interpretations."
)

PROMPTS = [
    {
        "name": "grounded_sql_analysis",
        "description": "Formulates and executes a verified, non-hallucinated SQL analysis against sovereign datasets with strict provenance citations.",
        "arguments": [
            {
                "name": "user_question",
                "description": "Natural language analytical question about sovereign datasets.",
                "required": True
            }
        ]
    },
    {
        "name": "dataset_provenance_audit",
        "description": "Inspects dataset schemas, contracts, dimensions, and null ratios ensuring complete factual grounding.",
        "arguments": [
            {
                "name": "dataset_uri",
                "description": "Dataset node URI or table triad to audit.",
                "required": True
            }
        ]
    }
]


def _extract_slug_from_uri(uri: str, fallback: str = "") -> str:
    clean = (uri or "").strip().rstrip("/")
    if clean.endswith("/index.md"):
        clean = clean[:-9]
    if "/" in clean:
        slug = clean.rsplit("/", 1)[-1]
        if slug:
            return slug.removesuffix(".md")
    return clean.removesuffix(".md") or re.sub(r"[^a-z0-9_\-]+", "_", fallback.lower()).strip("_")


def build_knowledge_graph_v2(catalog_url: Optional[str] = None) -> Dict[str, Any]:
    """Builds the Unified Semantic Knowledge Graph v2 across catalog entries and local bundles."""
    catalog = dm.discover(catalog_url)
    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")

    def _add_node(node_id: str, title: str, node_type: str, **extra: Any) -> None:
        if not node_id:
            return
        if node_id not in nodes_by_id:
            node = {"id": node_id, "title": title or node_id, "type": node_type}
            node.update({k: v for k, v in extra.items() if v is not None and v != ""})
            nodes_by_id[node_id] = node
        else:
            for k, v in extra.items():
                if v and not nodes_by_id[node_id].get(k):
                    nodes_by_id[node_id][k] = v

    def _add_edge(source: str, target: str, edge_type: str, label: str = "") -> None:
        if not source or not target:
            return
        key = (source, target, edge_type)
        if key not in seen_edges:
            seen_edges.add(key)
            edge: Dict[str, Any] = {"source": source, "target": target, "type": edge_type}
            if label:
                edge["label"] = label
            edges.append(edge)

    entries = catalog.get("entries", [])
    for entry in entries:
        node_id = entry.get("resolved_url") or entry.get("uri") or entry.get("title", "")
        title = entry.get("title", "")
        raw_desc = entry.get("description", "")
        domain_name = entry.get("domain", "")
        slug = _extract_slug_from_uri(entry.get("uri") or node_id, title)

        _add_node(
            node_id,
            title=title,
            node_type="dataset",
            slug=slug,
            domain=domain_name,
            description=raw_desc,
            catalog_source=entry.get("catalog_source", ""),
        )

        # Register declared resources in llms.txt entry
        for res_name in entry.get("resources") or []:
            triad = f"{slug}:{res_name}"
            _add_node(triad, title=res_name, node_type="resource", triad=triad, dataset=slug)
            _add_edge(node_id, triad, "HAS_RESOURCE", label="has_resource")

        # Extract markdown links from description
        for match in link_pattern.finditer(raw_desc):
            anchor_text, target = match.groups()
            target_type = "concept" if ("concept" in target or "wikidata.org" in target or target.startswith("wd:")) else "entity"
            _add_node(target, title=anchor_text, node_type=target_type)
            _add_edge(node_id, target, "MEASURES_CONCEPT" if target_type == "concept" else "REFERENCES", label=anchor_text)

    # Also scan local workspace bundles if available to enrich with fields, OpenAPI services, CLI tools, and SKOS concepts
    local_roots = [Path("knowledge/nodes"), Path("bundles"), Path("examples/bundles")]
    for root in local_roots:
        if not root.exists() or not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or not (child / "index.md").exists():
                continue
            try:
                dp = dm.get(str(child))
            except Exception:
                continue
            if not isinstance(dp, dict):
                continue
            manifest = dp.get("manifest") or {}
            slug = child.name
            ds_id = dp.get("id") or str(child)
            ds_type = str(manifest.get("type") or "dataset").lower()
            _add_node(ds_id, title=manifest.get("title") or slug, node_type=ds_type, slug=slug)

            # Lineage edges
            lineage_spec = manifest.get("lineage") or {}
            for src in lineage_spec.get("sources") or []:
                src_id = src.get("id") if isinstance(src, dict) else str(src)
                if src_id:
                    _add_edge(ds_id, src_id, "DERIVED_FROM", label="derived_from")

            # Resources & semantic columns
            for res in dp.get("resources") or []:
                if not isinstance(res, dict):
                    continue
                r_name = str(res.get("name") or "resource")
                triad = f"{slug}:{r_name}"
                _add_node(triad, title=r_name, node_type="resource", triad=triad, format=res.get("format", ""))
                _add_edge(ds_id, triad, "HAS_RESOURCE", label="has_resource")
                for f in res.get("fields") or []:
                    if isinstance(f, dict):
                        c_ref = str(f.get("concept") or f.get("rdfType") or "").strip()
                        if c_ref:
                            _add_node(c_ref, title=f.get("title") or f.get("name") or c_ref, node_type="concept")
                            _add_edge(triad, c_ref, "MEASURES_CONCEPT", label=str(f.get("name", "")))

            # Contracts: OpenAPI services & OWL-CLI tools
            for c in manifest.get("contracts") or []:
                if not isinstance(c, dict):
                    continue
                c_type = str(c.get("type") or "").lower()
                if c_type in ("owl-cli", "okf-cli") or c.get("binary"):
                    cmd = f"{c.get('binary', '')} {c.get('subcommand', '')}".strip() or "cli-tool"
                    cli_id = f"cli:{slug}:{cmd}"
                    _add_node(cli_id, title=cmd, node_type="cli_tool", binary=c.get("binary", ""))
                    _add_edge(ds_id, cli_id, "PROVIDES_TOOL", label=c_type or "owl-cli")
                    for inp in c.get("inputs") or []:
                        if isinstance(inp, dict) and inp.get("concept"):
                            c_ref = str(inp["concept"]).strip()
                            _add_node(c_ref, title=c_ref, node_type="concept")
                            _add_edge(cli_id, c_ref, "ACCEPTS_CONCEPT", label=str(inp.get("flag") or inp.get("name", "")))
                    outputs = c.get("outputs")
                    if isinstance(outputs, dict) and outputs.get("concept"):
                        c_ref = str(outputs["concept"]).strip()
                        _add_node(c_ref, title=c_ref, node_type="concept")
                        _add_edge(cli_id, c_ref, "RETURNS_CONCEPT", label=str(outputs.get("format", "stdout")))
                elif c_type == "openapi":
                    svc_id = f"service:{slug}:{c.get('path') or c.get('ref') or 'openapi'}"
                    _add_node(svc_id, title=f"OpenAPI Service ({slug})", node_type="service")
                    _add_edge(ds_id, svc_id, "PROVIDES_SERVICE", label="openapi")

            # SKOS / OWL concept anchors on the node itself
            for skos_uri in (manifest.get("skos") or []) + (manifest.get("exact_match") or []):
                if skos_uri:
                    _add_node(str(skos_uri), title=str(skos_uri), node_type="concept")
                    _add_edge(ds_id, str(skos_uri), "SKOS_MATCH", label="skos:exactMatch")

    nodes_list = list(nodes_by_id.values())
    return {
        "catalog_title": catalog.get("title", "Federated Catalog"),
        "nodes": nodes_list,
        "edges": edges,
        "total_nodes": len(nodes_list),
        "total_edges": len(edges),
    }


def build_semantic_context_map(query: str, catalog_url: Optional[str] = None) -> Dict[str, Any]:
    """Builds a 4-part Semantic Context Map in Markdown for a query across datasets, concepts, services, and CLIs."""
    matches = dm.search(query, catalog_url=catalog_url)
    kg = build_knowledge_graph_v2(catalog_url=catalog_url)
    q_norm = dm._normalize_search_text(query)
    q_tokens = q_norm.split()

    def _matches_tokens(text: str) -> bool:
        if not q_tokens:
            return True
        norm = dm._normalize_search_text(text)
        return all(t in norm for t in q_tokens)

    concept_nodes = [
        n for n in kg.get("nodes", [])
        if n.get("type") == "concept" and _matches_tokens(f"{n.get('id', '')} {n.get('title', '')}")
    ]
    service_nodes = [
        n for n in kg.get("nodes", [])
        if n.get("type") == "service" and _matches_tokens(f"{n.get('id', '')} {n.get('title', '')}")
    ]
    cli_nodes = [
        n for n in kg.get("nodes", [])
        if n.get("type") == "cli_tool" and _matches_tokens(f"{n.get('id', '')} {n.get('title', '')}")
    ]

    md_lines = [f"# Mapa de Contexto Semántico: `{query}`", ""]

    # 1. ¿Qué significa? (Conceptos SKOS / OWL)
    md_lines.append("## 1. ¿Qué significa? (Conceptos Semánticos SKOS / OWL)")
    if concept_nodes:
        for cn in concept_nodes[:10]:
            md_lines.append(f"- **`{cn.get('title')}`** (`{cn.get('id')}`)")
    else:
        md_lines.append(f"- Búsqueda léxica/semántica directa sobre el término `{query}`.")
    md_lines.append("")

    # 2. ¿Dónde están los datos estáticos? (Datasets y Tríadas SQL)
    md_lines.append("## 2. ¿Dónde están los datos estáticos? (Datasets y Tríadas SQL)")
    triads_found: List[str] = []
    if matches:
        md_lines.append("| Dataset / Nodo | Dominio | Recursos / Tríadas SQL | Consulta Inicial |")
        md_lines.append("| :--- | :--- | :--- | :--- |")
        for m in matches[:15]:
            title = m.get("title", "")
            uri = m.get("uri") or m.get("resolved_url", "")
            slug = _extract_slug_from_uri(uri, title)
            dom = m.get("domain") or "General"
            recs = m.get("resources") or []
            if recs:
                triad_list = [f"`{slug}:{r}`" for r in recs]
                first_triad = f"{slug}:{recs[0]}"
                triads_found.append(first_triad)
                q_sql = f'`SELECT * FROM "{first_triad}" LIMIT 10`'
                md_lines.append(f"| **{title}** (`{slug}`) | {dom} | {', '.join(triad_list)} | {q_sql} |")
            else:
                md_lines.append(f"| **{title}** (`{slug}`) | {dom} | *(Inspeccionar con `datamesh_get_dataproduct(uri=\"{slug}\")`)* | — |")
    else:
        md_lines.append("- No se encontraron datasets estáticos que coincidan con la consulta.")
    md_lines.append("")

    # 3. ¿Qué Servicios Remotos (OpenAPI) o CLIs Locales (OWL-CLI) operan sobre este concepto?
    md_lines.append("## 3. Servicios Remotos (`OpenAPI`) y Herramientas CLI (`owl-cli`)")
    if service_nodes or cli_nodes:
        for sn in service_nodes:
            md_lines.append(f"- **Servicio OpenAPI**: `{sn.get('title')}` (`{sn.get('id')}`)")
        for cn in cli_nodes:
            md_lines.append(f"- **Herramienta CLI (`owl-cli`)**: `{cn.get('title')}` (`{cn.get('id')}`)")
    else:
        md_lines.append("- Ningún servicio OpenAPI o binario CLI registrado directamente bajo este término en el catálogo activo.")
    md_lines.append("")

    # 4. ¿Cómo cruzar tablas heterogéneas? (Joins Semánticos SQL)
    md_lines.append("## 4. Sugerencia de Cruce Semántico (Cross-Dataset SQL Join)")
    if len(triads_found) >= 2:
        t_a, t_b = triads_found[0], triads_found[1]
        md_lines.append(
            f"Puedes cruzar las tríadas descubiertas en DuckDB usando dimensiones compartidas o `dm.generate_cross_dataset_join_sql(...)`:\n"
            f"```sql\n"
            f"SELECT a.*, b.*\n"
            f'FROM "{t_a}" AS a\n'
            f'JOIN "{t_b}" AS b\n'
            f"  ON a.departamento = b.departamento\n"
            f"LIMIT 20;\n"
            f"```"
        )
    else:
        md_lines.append("- Inspecciona el esquema detallado de cualquier nodo con `datamesh_get_dataproduct` para ver sus columnas y enlaces SKOS.")

    return {
        "query": query,
        "total_datasets": len(matches),
        "datasets": matches,
        "concepts": concept_nodes,
        "services": service_nodes,
        "cli_tools": cli_nodes,
        "context_markdown": "\n".join(md_lines),
    }


def handle_jsonrpc(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = request.get("method")
    # JSON-RPC 2.0 strict conformance: Notifications (missing "id", id is None, or notifications/*)
    # MUST NEVER receive a response object.
    if (
        "id" not in request
        or request.get("id") is None
        or (isinstance(method, str) and method.startswith("notifications/"))
        or method == "initialized"
    ):
        return None

    msg_id = request.get("id")
    params = request.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "prompts": {}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                    "instructions": GUARDRAILS_INSTRUCTIONS
                }
            }
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "prompts": PROMPTS
            }
        }

    if method == "prompts/get":
        prompt_name = params.get("name")
        args = params.get("arguments", {})
        if prompt_name == "grounded_sql_analysis":
            q = args.get("user_question", "")
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "description": "Strictly grounded SQL query workflow",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": (
                                    f"Analyze the following question: '{q}'.\n"
                                    "STRICT GUARDRAILS:\n"
                                    "1. First call datamesh_search_catalog or datamesh_get_dataproduct to confirm table and column names.\n"
                                    "2. Run datamesh_sql_query with precise SQL.\n"
                                    "3. Base your final response ONLY on the rows returned. Cite the dataset triad. Never hallucinate numbers."
                                )
                            }
                        }
                    ]
                }
            }
        elif prompt_name == "dataset_provenance_audit":
            ds = args.get("dataset_uri", "")
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "description": "Audit dataset conformance and structure",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": f"Audit dataset '{ds}' using datamesh_get_dataproduct and datamesh_sql_query. Verify dimensions, column types, row counts, and null presence without assumptions."
                            }
                        }
                    ]
                }
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Prompt not found: {prompt_name}"}
            }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": TOOLS
            }
        }

    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments") or {}

        try:
            if tool_name == "datamesh_discover_catalogs":
                catalog_url = args.get("catalog_url")
                data = dm.discover(catalog_url)
                return make_tool_result(msg_id, data)

            elif tool_name == "datamesh_search_catalog":
                keyword = args.get("keyword", "")
                catalog_url = args.get("catalog_url")
                data = dm.search(keyword, catalog_url)
                return make_tool_result(msg_id, data)

            elif tool_name == "datamesh_resolve_context":
                query = args.get("query") or args.get("keyword") or ""
                catalog_url = args.get("catalog_url")
                data = build_semantic_context_map(query, catalog_url=catalog_url)
                return make_tool_result(msg_id, data)

            elif tool_name == "datamesh_get_dataproduct":
                uri = args.get("uri", "")
                include_code_blocks = bool(args.get("include_code_blocks", False))
                insecure = bool(args.get("insecure", False))
                if insecure:
                    os.environ["DATAMESH_INSECURE_TLS"] = "1"
                data = dict(dm.get(uri))
                # Remove duplicate raw_content to save agent context window tokens
                data.pop("raw_content", None)
                manifest = data.get("manifest") or {}
                if not data.get("title") and manifest.get("title"):
                    data["title"] = manifest["title"]
                if not include_code_blocks and data.get("description"):
                    data["description"] = strip_ojs_blocks(str(data["description"]))
                return make_tool_result(msg_id, data)

            elif tool_name == "datamesh_query_resource":
                resource_uri = args.get("resource_uri", "")
                if is_forbidden_local_ref(resource_uri):
                    return make_tool_error(
                        msg_id,
                        "Local filesystem paths are not allowed; provide an http(s) URL or a catalog triad.",
                    )
                if resource_uri.startswith(("http://", "https://")):
                    try:
                        validate_proxy_url(resource_uri)
                    except (ValueError, PermissionError) as guard_err:
                        return make_tool_error(msg_id, str(guard_err))
                filters = args.get("filters")
                limit = args.get("limit")
                insecure = bool(args.get("insecure", False))
                if insecure:
                    os.environ["DATAMESH_INSECURE_TLS"] = "1"
                try:
                    data = dm.query(resource_uri, filters=filters, limit=limit, insecure=insecure)
                    return make_tool_result(msg_id, data)
                except Exception as q_err:
                    err_msg = str(q_err)
                    if "ssl" in err_msg.lower() or "certificate" in err_msg.lower():
                        err_msg += (
                            "\n[TIP] TLS certificate verification failed. Call this tool with "
                            "\"insecure\": true to bypass certificate verification for this endpoint."
                        )
                    return make_tool_error(msg_id, err_msg)

            elif tool_name in ("datamesh_sql_query", "query_sql"):
                sql_query = args.get("sql_query") or args.get("sql") or ""
                insecure = bool(args.get("insecure", False))
                if insecure:
                    os.environ["DATAMESH_INSECURE_TLS"] = "1"
                try:
                    data = dm.sql(sql_query, insecure=insecure)
                    return make_tool_result(msg_id, data)
                except Exception as sql_err:
                    err_msg = str(sql_err)
                    if "ssl" in err_msg.lower() or "certificate" in err_msg.lower():
                        err_msg += (
                            "\n[TIP] TLS certificate verification failed. Call this tool with "
                            "\"insecure\": true to bypass certificate verification for this endpoint."
                        )
                    return make_tool_error(msg_id, err_msg)

            elif tool_name in ("read_resource", "datamesh_read_resource"):
                resource_uri = args.get("resource_uri") or args.get("uri") or ""
                limit = args.get("limit")

                if is_forbidden_local_ref(resource_uri):
                    return make_tool_error(
                        msg_id,
                        "Local filesystem paths are not allowed; provide an http(s) URL or a catalog triad.",
                    )
                if resource_uri.startswith(("http://", "https://")):
                    try:
                        validate_proxy_url(resource_uri)
                    except (ValueError, PermissionError) as guard_err:
                        return make_tool_error(msg_id, str(guard_err))

                insecure = bool(args.get("insecure", False))
                try:
                    resolved = dm.resolve_resource(resource_uri, insecure=insecure)
                    if resolved and resolved.local_path and os.path.exists(resolved.local_path):
                        import duckdb
                        local_p = str(resolved.local_path)
                        fmt = (resolved.format or "").lower()

                        if local_p.lower().endswith(".zip") or fmt == "zip":
                            from datamesh.adapters.storage.zip_extractor import extract_zip_tabular_resource
                            target_hint = None
                            if resolved.descriptor:
                                target_hint = resolved.descriptor.resource or resolved.descriptor.raw_reference
                            if not target_hint:
                                target_hint = os.path.basename(resource_uri)
                            extracted_p, z_fmt = extract_zip_tabular_resource(
                                local_p,
                                target_hint=target_hint,
                                preview_limit=int(limit) if limit else 50,
                            )
                            if extracted_p:
                                local_p = extracted_p
                                if z_fmt:
                                    fmt = z_fmt

                        _ = fmt
                        read_clause = read_expression(local_p)

                        limit_clause = f" LIMIT {int(limit)}" if limit else ""
                        df = duckdb.query(f"SELECT * FROM {read_clause}{limit_clause}").to_df()
                        cols = list(df.columns)
                        rows = df.astype(str).values.tolist()
                        return make_tool_result(msg_id, {
                            "columns": cols,
                            "rows": rows,
                            "row_count": len(rows),
                            "format": fmt or "tabular",
                        })
                except Exception as res_err:
                    sys.stderr.write(f"[mcp read_resource] Resolver conversion failed: {res_err}\n")

                res = dm.query(resource_uri, limit=limit)
                return make_tool_result(msg_id, res)

            elif tool_name == "datamesh_discover_endpoint":
                url = args.get("url", "")
                disc = dm.discover_endpoint(url)
                if not disc:
                    return make_tool_error(msg_id, f"Could not discover endpoint at {url}")
                return make_tool_result(msg_id, {
                    "schema_version": disc.schema_version,
                    "catalog": {
                        "name": disc.catalog.name,
                        "title": disc.catalog.title,
                        "type": disc.catalog.catalog_type,
                        "catalog_url": disc.catalog.catalog_url,
                        "api_endpoint": disc.catalog.api_endpoint,
                    },
                    "auth": {
                        "type": disc.auth.auth_type,
                        "required": disc.auth.required,
                    },
                    "capabilities": disc.capabilities,
                })

            elif tool_name == "datamesh_harvest_ckan":
                url = args.get("url", "")
                query = args.get("query", "")
                limit = int(args.get("limit", 10))
                harvest_res = dm.harvest_ckan(url, query=query, limit=limit)
                return make_tool_result(msg_id, {
                    "catalog_url": harvest_res.catalog_url,
                    "total_discovered": harvest_res.total_discovered,
                    "harvested_count": len(harvest_res.harvested_packages),
                    "packages": [p["name"] for p in harvest_res.harvested_packages],
                })

            elif tool_name == "datamesh_get_lineage":
                dataset_id = args.get("dataset_id")
                catalog_url = args.get("catalog_url")
                if dataset_id:
                    res = dm.get_lineage(dataset_id, catalog_url=catalog_url)
                    return make_tool_result(msg_id, res)
                else:
                    g = dm.lineage(catalog_url=catalog_url)
                    return make_tool_result(msg_id, g.to_dict())

            elif tool_name == "datamesh_read_concept_body":
                uri = args.get("uri", "")
                include_code_blocks = bool(args.get("include_code_blocks", False))
                data = dm.get(uri)
                if not data:
                    return make_tool_error(msg_id, f"Concept '{uri}' not found.")
                manifest = data.get("manifest") or {}
                title = data.get("title") or manifest.get("title") or ""
                if include_code_blocks and data.get("raw_content"):
                    raw_c = str(data.get("raw_content", ""))
                    parts = raw_c.split("---", 2)
                    body = parts[2].strip() if len(parts) >= 3 else raw_c.strip()
                    desc = str(data.get("description") or "")
                    if "## Contrato de Datos y Esquema Semántico" in desc and "## Contrato de Datos y Esquema Semántico" not in body:
                        synth_part = desc.split("## Contrato de Datos y Esquema Semántico", 1)[1]
                        body = f"{body}\n\n## Contrato de Datos y Esquema Semántico{synth_part}".strip()
                else:
                    body = str(data.get("description") or data.get("raw_content") or "")
                    if body.startswith("---"):
                        parts = body.split("---", 2)
                        if len(parts) >= 3:
                            body = parts[2].strip()
                    body = strip_ojs_blocks(body)
                return make_tool_result(msg_id, {
                    "uri": data.get("id") or uri,
                    "title": title,
                    "markdown_body": body,
                })

            elif tool_name == "datamesh_get_knowledge_graph":
                catalog_url = args.get("catalog_url")
                kg_data = build_knowledge_graph_v2(catalog_url=catalog_url)
                return make_tool_result(msg_id, kg_data)

            elif tool_name == "datamesh_handshake":
                from datamesh.server import process_handshake
                data = process_handshake(args)
                return make_tool_result(msg_id, data)

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method or tool not found: {tool_name}"
                    }
                }
        except Exception as e:
            return make_tool_error(msg_id, str(e))

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {
            "code": -32601,
            "message": f"Method not supported: {method}"
        }
    }


def make_tool_result(msg_id: Any, data: Any) -> Dict[str, Any]:
    text_content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": text_content
                }
            ],
            "isError": False
        }
    }


def make_tool_error(msg_id: Any, error_msg: str) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": f"Error executing tool: {error_msg}"
                }
            ],
            "isError": True
        }
    }


def run_mcp_server():
    """Runs the MCP server over standard input/output."""
    sys.stderr.write(f"[{SERVER_NAME}] Server started (stdio mode)\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line_str = line.strip()
        if not line_str:
            continue
        try:
            req = json.loads(line_str)
            if not isinstance(req, dict):
                continue
            resp = handle_jsonrpc(req)
            if resp is not None and resp.get("id") is not None:
                sys.stdout.write(json.dumps(resp, default=str) + "\n")
                sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"[{SERVER_NAME}] Ignoring malformed JSON-RPC line: {e}\n")
            sys.stderr.flush()
