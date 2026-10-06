from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class StorageConfig:
    """Configuration parameters for generic ~/.datamesh and ~/datamesh storage."""
    home_dir: Path
    cache_dir: Path
    config_file: Path
    max_cache_size_bytes: int = 10 * 1024 * 1024 * 1024  # 10 GB
    default_ttl_seconds: int = 86400 * 7  # 7 days

    @classmethod
    def default(cls) -> StorageConfig:
        from datamesh.constants import get_datamesh_home, get_cache_dir
        home = get_datamesh_home()
        cache = get_cache_dir()
        config_path = home / "config.yaml"
        return cls(
            home_dir=home,
            cache_dir=cache,
            config_file=config_path,
        )

@dataclass(frozen=True)
class CanonicalURI:
    """Represents a standardized sovereign URI '[catalog:]dataset:resource' or 'datamesh://...'."""
    dataset: str
    resource: str
    catalog: Optional[str] = None

    @classmethod
    def parse(cls, raw: str) -> Optional[CanonicalURI]:
        trimmed = raw.strip().strip("'\"`")
        if not trimmed:
            return None
        # 1. datamesh:// or odkf:// scheme
        if trimmed.startswith(("datamesh://", "odkf://")):
            clean = trimmed.split("://", 1)[1]
            parts = [p.strip() for p in clean.split("/") if p.strip()]
            if len(parts) >= 3:
                return cls(catalog=parts[0], dataset=parts[1], resource=parts[2])
            elif len(parts) == 2:
                return cls(catalog=None, dataset=parts[0], resource=parts[1])
            return None

        # 2. HTTP/HTTPS or file URLs containing /datasets/<dataset>/<resource> or /nodes/<dataset>/<resource>
        if trimmed.startswith(("http://", "https://", "file://")):
            # Match e.g. .../datasets/cartera-creditos/creditos.csv or .../nodes/elecciones/votos.parquet
            match = re.search(r'/(?:datasets|nodes)/([^/]+)/([^/?#]+)', trimmed)
            if match:
                ds = match.group(1).strip()
                res_raw = match.group(2).strip()
                res = res_raw.rsplit(".", 1)[0] if "." in res_raw else res_raw
                return cls(catalog=None, dataset=ds, resource=res)
            # Match generic URL ending with /<dataset>/<resource.ext>
            parsed_path = trimmed.split("?")[0].split("#")[0].rstrip("/")
            path_parts = [p for p in parsed_path.split("/") if p]
            if len(path_parts) >= 2:
                ds = path_parts[-2]
                res_raw = path_parts[-1]
                res = res_raw.rsplit(".", 1)[0] if "." in res_raw else res_raw
                return cls(catalog=None, dataset=ds, resource=res)

        # 3. Colon-separated format ('cat:ds:res' or 'ds:res')
        if ":" in trimmed:
            parts = trimmed.split(":")
            if len(parts) == 3:
                return cls(catalog=parts[0].strip(), dataset=parts[1].strip(), resource=parts[2].strip())
            elif len(parts) == 2:
                return cls(catalog=None, dataset=parts[0].strip(), resource=parts[1].strip())

        # 4. Slash-separated format ('cat/ds/res' or 'ds/res')
        if "/" in trimmed:
            parts = [p.strip() for p in trimmed.split("/") if p.strip()]
            if len(parts) == 3:
                return cls(catalog=parts[0], dataset=parts[1], resource=parts[2])
            elif len(parts) == 2:
                return cls(catalog=None, dataset=parts[0], resource=parts[1])

        return None

    @property
    def triad(self) -> str:
        if self.catalog:
            return f"{self.catalog}:{self.dataset}:{self.resource}"
        return f"{self.dataset}:{self.resource}"

    @property
    def full_uri(self) -> str:
        if self.catalog:
            return f"datamesh://{self.catalog}/{self.dataset}/{self.resource}"
        return f"datamesh://{self.dataset}/{self.resource}"

@dataclass(frozen=True)
class ResourceDescriptor:
    """Value object describing a target resource to resolve."""
    raw_reference: str
    dataset: Optional[str] = None
    resource: Optional[str] = None
    format: Optional[str] = None  # parquet, csv, tsv, json, jsonl
    source_service: str = "unknown"  # local, github, kaggle, http, git

@dataclass(frozen=True)
class CacheEntryMetadata:
    """Metadata recorded for every cached resource."""
    key: str
    original_uri: str
    local_path: str
    format: str
    size_bytes: int
    cached_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    etag: Optional[str] = None
    sha256: Optional[str] = None
    source_service: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "original_uri": self.original_uri,
            "local_path": self.local_path,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "cached_at": self.cached_at,
            "etag": self.etag,
            "sha256": self.sha256,
            "source_service": self.source_service,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CacheEntryMetadata:
        return cls(
            key=data["key"],
            original_uri=data["original_uri"],
            local_path=data["local_path"],
            format=data.get("format", "csv"),
            size_bytes=data.get("size_bytes", 0),
            cached_at=data.get("cached_at", datetime.now(timezone.utc).isoformat()),
            etag=data.get("etag"),
            sha256=data.get("sha256"),
            source_service=data.get("source_service", "unknown"),
        )

@dataclass(frozen=True)
class ResolvedResource:
    """Represents a resolved and downloaded physical resource ready for DuckDB execution."""
    descriptor: ResourceDescriptor
    local_path: Path
    format: str  # parquet, csv, tsv, json, jsonl
    is_cached: bool = False
    metadata: Optional[CacheEntryMetadata] = None


@dataclass(frozen=True)
class SpatialCoverage:
    """Standardized spatial coverage conforming to W3C DCAT v3 / ISO 19115."""
    country: Optional[str] = None          # ISO 3166-1 alpha-2 (e.g. 'BO')
    regions: tuple[str, ...] = ()          # ISO 3166-2 (e.g. ('BO-L', 'BO-C', 'BO-S'))
    bbox: Optional[tuple[float, float, float, float]] = None # (minX, minY, maxX, maxY) EPSG:4326
    geometry: Optional[Dict[str, Any]] = None # GeoJSON geometry object
    granularity: Optional[str] = None      # country | region | municipality | point

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.country:
            out["country"] = self.country
        if self.regions:
            out["regions"] = list(self.regions)
        if self.bbox:
            out["bbox"] = list(self.bbox)
        if self.geometry:
            out["geometry"] = self.geometry
        if self.granularity:
            out["granularity"] = self.granularity
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SpatialCoverage:
        regions_raw = data.get("regions") or ()
        if isinstance(regions_raw, list):
            regions = tuple(str(r) for r in regions_raw)
        else:
            regions = ()
        bbox_raw = data.get("bbox")
        bbox = tuple(float(x) for x in bbox_raw) if isinstance(bbox_raw, (list, tuple)) and len(bbox_raw) == 4 else None
        return cls(
            country=data.get("country"),
            regions=regions,
            bbox=bbox,
            geometry=data.get("geometry") if isinstance(data.get("geometry"), dict) else None,
            granularity=data.get("granularity"),
        )


@dataclass(frozen=True)
class TemporalCoverage:
    """Standardized temporal coverage conforming to ISO 8601 and W3C DCAT."""
    start: Optional[str] = None            # ISO 8601 start date/time
    end: Optional[str] = None              # ISO 8601 end date/time
    frequency: Optional[str] = None        # daily | weekly | monthly | annual | irregular | streaming
    timezone: Optional[str] = None         # e.g. 'America/La_Paz'

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.start:
            out["start"] = self.start
        if self.end:
            out["end"] = self.end
        if self.frequency:
            out["frequency"] = self.frequency
        if self.timezone:
            out["timezone"] = self.timezone
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TemporalCoverage:
        return cls(
            start=data.get("start"),
            end=data.get("end"),
            frequency=data.get("frequency"),
            timezone=data.get("timezone"),
        )


@dataclass(frozen=True)
class SemanticFieldMapping:
    """Maps raw column categories to ODKF Knowledge Base concept IDs without changing raw files."""
    field_name: str
    concept_ref: Optional[str] = None      # Local relative path or concept identifier, e.g. 'concepts/departamentos.md'
    value_mapping: Dict[str, str] = field(default_factory=dict) # e.g. {'LPZ': 'concept:departamentos:la_paz'}

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"field_name": self.field_name}
        if self.concept_ref:
            out["concept_ref"] = self.concept_ref
        if self.value_mapping:
            out["value_mapping"] = dict(self.value_mapping)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SemanticFieldMapping:
        return cls(
            field_name=data.get("field_name", ""),
            concept_ref=data.get("concept_ref") or data.get("concept"),
            value_mapping=data.get("value_mapping") or {},
        )


@dataclass(frozen=True)
class QualityCheckRule:
    """Quality rule declaration for Frictionless / DataMesh quality evaluation."""
    rule: str                              # no_nulls | unique | range | regex | custom
    target_field: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = {"rule": self.rule}
        if self.target_field:
            out["field"] = self.target_field
        if self.params:
            out.update(self.params)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QualityCheckRule:
        rule = data.get("rule", "custom")
        f = data.get("field") or data.get("target_field")
        params = {k: v for k, v in data.items() if k not in ("rule", "field", "target_field")}
        return cls(rule=rule, target_field=f, params=params)


@dataclass(frozen=True)
class QualityProfile:
    """Data quality and completeness profile."""
    status: str = "curated"                # raw | curated | verified | official
    completeness: Optional[float] = None   # Ratio between 0.0 and 1.0
    row_count: Optional[int] = None
    checks: tuple[QualityCheckRule, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"status": self.status}
        if self.completeness is not None:
            out["completeness"] = self.completeness
        if self.row_count is not None:
            out["row_count"] = self.row_count
        if self.checks:
            out["checks"] = [c.to_dict() for c in self.checks]
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QualityProfile:
        checks_raw = data.get("checks") or ()
        checks = tuple(QualityCheckRule.from_dict(c) for c in checks_raw if isinstance(c, dict))
        return cls(
            status=data.get("status", "curated"),
            completeness=float(data["completeness"]) if "completeness" in data and data["completeness"] is not None else None,
            row_count=int(data["row_count"]) if "row_count" in data and data["row_count"] is not None else None,
            checks=checks,
        )


@dataclass(frozen=True)
class PublicationTargetResult:
    """Result of publishing a dataset or bundle to a specific platform."""
    target: str                            # portal | local | kaggle | github
    success: bool
    destination_uri: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class KeycloakAuth:
    """Keycloak / OpenID Connect endpoint specifications."""
    realm_url: str
    token_endpoint: str
    authorization_endpoint: Optional[str] = None
    client_id: Optional[str] = None
    scopes_supported: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KeycloakAuth:
        return cls(
            realm_url=data.get("realm_url", ""),
            token_endpoint=data.get("token_endpoint", ""),
            authorization_endpoint=data.get("authorization_endpoint"),
            client_id=data.get("client_id"),
            scopes_supported=tuple(data.get("scopes_supported", ())),
        )


@dataclass(frozen=True)
class APIKeyAuth:
    """API Key / Token header configuration."""
    header_name: str = "X-CKAN-API-Key"
    prefix: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> APIKeyAuth:
        return cls(
            header_name=data.get("header_name", "X-CKAN-API-Key"),
            prefix=data.get("prefix", ""),
        )


@dataclass(frozen=True)
class AuthConfiguration:
    """Authentication configuration for catalog discovery."""
    auth_type: str = "none"                # none | api_key | bearer | basic | oauth2 | keycloak
    required: bool = False
    keycloak: Optional[KeycloakAuth] = None
    api_key: Optional[APIKeyAuth] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AuthConfiguration:
        kc = KeycloakAuth.from_dict(data["keycloak"]) if data.get("keycloak") else None
        ak = APIKeyAuth.from_dict(data["api_key"]) if data.get("api_key") else None
        return cls(
            auth_type=data.get("type", "none"),
            required=bool(data.get("required", False)),
            keycloak=kc,
            api_key=ak,
        )


@dataclass(frozen=True)
class CatalogMetadata:
    """Catalog metadata announced in well-known discovery."""
    name: str
    title: str
    catalog_url: str
    catalog_type: str = "ckan"             # ckan | okf | dcat | git
    description: Optional[str] = None
    api_endpoint: Optional[str] = None
    version: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CatalogMetadata:
        return cls(
            name=data.get("name", ""),
            title=data.get("title", ""),
            catalog_url=data.get("catalog_url", ""),
            catalog_type=data.get("type", "ckan"),
            description=data.get("description"),
            api_endpoint=data.get("api_endpoint"),
            version=data.get("version"),
        )


@dataclass(frozen=True)
class WellKnownDiscovery:
    """Normalized /.well-known/datamesh.json document."""
    schema_version: str
    catalog: CatalogMetadata
    auth: AuthConfiguration
    capabilities: Dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WellKnownDiscovery:
        return cls(
            schema_version=data.get("schema_version", "0.2.0"),
            catalog=CatalogMetadata.from_dict(data.get("catalog", {})),
            auth=AuthConfiguration.from_dict(data.get("auth", {})),
            capabilities=dict(data.get("capabilities", {})),
        )


@dataclass(frozen=True)
class CKANResource:
    """Resource in a CKAN dataset package."""
    id: str
    name: str
    url: str
    format: str = "csv"
    description: Optional[str] = None
    mimetype: Optional[str] = None
    size: Optional[int] = None
    datastore_active: bool = False
    fields: tuple[Dict[str, str], ...] = ()


@dataclass(frozen=True)
class CKANPackage:
    """Dataset package retrieved from CKAN Action API v3."""
    id: str
    name: str
    title: str
    notes: Optional[str] = None
    url: Optional[str] = None
    version: Optional[str] = None
    organization_title: Optional[str] = None
    tags: tuple[str, ...] = ()
    extras: Dict[str, Any] = field(default_factory=dict)
    resources: tuple[CKANResource, ...] = ()


@dataclass(frozen=True)
class CKANHarvestResult:
    """Summary of harvested CKAN packages and OKF artifacts."""
    catalog_url: str
    total_discovered: int
    harvested_packages: tuple[Dict[str, Any], ...] = ()
    output_directory: Optional[str] = None
    execution_time_ms: int = 0


@dataclass(frozen=True)
class CategoryConceptMapping:
    """Mapping of a specific categorical column value to an OKF / SKOS concept."""
    value: str
    label: str
    concept: Optional[str] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class KnowledgeConceptDoc:
    """OKF / ODKF v0.2 Knowledge concept document with SKOS metadata."""
    id: str
    title: str
    pref_label: str
    description: Optional[str] = None
    alt_labels: tuple[str, ...] = ()
    exact_match: Optional[str] = None  # Wikidata URI or ontology URI
    broader: Optional[str] = None
    related: tuple[str, ...] = ()
    body_markdown: str = ""
    categories: tuple[CategoryConceptMapping, ...] = ()

    def to_markdown(self) -> str:
        """Render OKF v0.2 SKOS markdown file with YAML frontmatter."""
        lines = [
            "---",
            "type: concept",
            f"title: \"{self.title}\"",
            "skos:",
            f"  prefLabel: \"{self.pref_label}\"",
        ]
        if self.alt_labels:
            alt_list = ", ".join(f'"{al}"' for al in self.alt_labels)
            lines.append(f"  altLabel: [{alt_list}]")
        if self.exact_match:
            lines.append(f"  exactMatch: \"{self.exact_match}\"")
        if self.broader:
            lines.append(f"  broader: \"{self.broader}\"")
        if self.related:
            rel_list = ", ".join(f'"{r}"' for r in self.related)
            lines.append(f"  related: [{rel_list}]")
        lines.append("---")
        lines.append("")
        lines.append(f"# {self.title}")
        lines.append("")
        if self.description:
            lines.append(f"{self.description}")
            lines.append("")
        if self.body_markdown:
            lines.append(self.body_markdown)
            lines.append("")
        if self.categories:
            lines.append("## Categorías y Valores")
            lines.append("")
            lines.append("| Código / Valor | Etiqueta / Significado | Concepto Vinculado | Descripción |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for c in self.categories:
                c_link = f"[{c.concept}]({c.concept})" if c.concept else "—"
                desc = c.description or "—"
                lines.append(f"| `{c.value}` | **{c.label}** | {c_link} | {desc} |")
            lines.append("")
        return "\n".join(lines)


@dataclass(frozen=True)
class DataPackageBuildResult:
    """Result of creating or updating a DataPackage manifest and associated concepts."""
    name: str
    title: str
    datapackage: Dict[str, Any]
    yaml_content: str
    output_path: Optional[str] = None
    generated_concepts: tuple[KnowledgeConceptDoc, ...] = ()



