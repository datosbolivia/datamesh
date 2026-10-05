export interface ResourceTriad {
  catalog?: string;
  dataset: string;
  resource: string;
}

export interface CatalogEntry {
  title: string;
  uri: string;
  resolved_url: string;
  description: string;
  domain: string;
  resources?: string[];
  catalog_source?: string;
}

export interface Catalog {
  title: string;
  description: string;
  source_url?: string;
  source_catalogs?: string[];
  entries: CatalogEntry[];
}

export interface ResourceField {
  name: string;
  type: string;
  description?: string;
  format?: string;
  constraints?: Record<string, any>;
  concept?: string;
  value_mapping?: Record<string, string>;
  categories?: Record<string, string> | Array<{ value: string; concept?: string; id?: string }>;
}

export interface SpatialCoverage {
  country?: string;
  regions?: string[];
  bbox?: [number, number, number, number];
  geometry?: Record<string, any>;
  granularity?: "country" | "region" | "municipality" | "point" | string;
}

export interface TemporalCoverage {
  start?: string;
  end?: string;
  frequency?: "daily" | "weekly" | "monthly" | "annual" | "irregular" | "streaming" | string;
  timezone?: string;
}

export interface QualityProfile {
  status?: "raw" | "curated" | "verified" | "official" | string;
  completeness?: number;
  row_count?: number;
  checks?: Array<{ rule: string; field?: string; [key: string]: any }>;
}

export interface DataResource {
  name: string;
  path: string;
  format?: string;
  mediatype?: string;
  schema?: {
    fields?: ResourceField[];
  };
  policy?: string;
  description?: string;
  container_path?: string;
  container_mediatype?: string;
  resources?: DataResource[];
}

export interface DataPackage {
  name?: string;
  title?: string;
  description?: string;
  spatial?: SpatialCoverage;
  temporal?: TemporalCoverage;
  quality?: QualityProfile;
  resources: DataResource[];
}

export interface Contract {
  type: string;
  path: string;
}

export interface Manifest {
  type: string;
  title: string;
  dimensions: string[];
  contracts?: Contract[];
  lineage: {
    sources?: string[];
    version: string;
    updated_at?: string;
  };
}

export interface DataProduct {
  id: string;
  manifest: Manifest;
  description: string;
  raw_content?: string;
}

export interface ValidationIssue {
  code: string;
  severity: "ERROR" | "WARNING" | "INFO";
  message: string;
  path?: string;
  line?: number;
}

export interface ValidationReport {
  valid: boolean;
  target: string;
  total_errors: number;
  total_warnings: number;
  issues: ValidationIssue[];
}

export interface QueryRequest {
  resource_uri?: string;
  filters?: Record<string, string>;
  search?: string;
  sort_by?: string;
  sort_direction?: "asc" | "desc";
  limit?: number;
  offset?: number;
  proxy_url?: string;
}

export interface QueryResult {
  columns: string[];
  rows: string[][];
  row_count: number;
  total_count: number;
  engine?: string;
}

export type ExecutionEngine = "duckdb" | "in-memory" | "hyparquet";

export interface DatasetContext {
  dataset?: string;
  slug?: string;
  resources?: Array<{ name?: string; path?: string; [key: string]: any }>;
}

export interface DataMeshClientOptions {
  catalogUrls?: string[];
  engine?: ExecutionEngine;
  proxyUrl?: string;
  defaultDataset?: string;
  defaultResources?: Array<{ name?: string; path?: string; [key: string]: any }>;
}

/**
 * Standard sovereign endpoints for OKF / ODKF v0.2 catalogs and portals.
 */
export const CANONICAL_ENDPOINTS = {
  LLMS_TXT: "/llms.txt",
  LLM_TXT: "/llm.txt",
  LLMS_FULL_TXT: "/llms-full.txt",
  RAW: "/raw",
} as const;

/**
 * Matches table names in FROM and JOIN clauses (quoted or unquoted).
 */
export const TABLE_REF_PATTERN = /\b(?:FROM|JOIN)\s+(?:ONLY\s+)?(?:["']([^"']+)["']|([a-zA-Z0-9_\-\.:/]+))/gi;

/**
 * Matches quoted identifiers with colons (canonical triads).
 */
export const QUOTED_COLON_PATTERN = /["']([^"':\s]+:[^"']+)["']/g;

/**
 * Matches quoted identifiers with slashes (slash-separated triads or relative paths).
 */
export const QUOTED_SLASH_PATTERN = /["']([^"'\s]+\/[^"'\s]+)["']/g;

/**
 * Sanitizes text replacing non-alphanumeric chars with underscores.
 */
export function slugify(text: string): string {
  return text.toLowerCase().replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}

/**
 * Known domains and suffixes with strict browser CORS restrictions.
 */
export const KNOWN_CORS_RESTRICTED_DOMAINS: string[] = [
  'kaggle.com',
  'docs.google.com',
  'drive.google.com',
  'sheets.googleapis.com',
  'dropbox.com',
  'onedrive.live.com',
  '1drv.ms',
  'gob.bo',
  'bo',
];

/**
 * Standard CORS proxy templates.
 */
export const DEFAULT_PROXY_PROVIDERS: Record<string, (url: string) => string> = {
  local: (url: string) => `http://localhost:8000/proxy?url=${encodeURIComponent(url)}`,
  allorigins: (url: string) => `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`,
  corsproxy: (url: string) => `https://corsproxy.io/?url=${encodeURIComponent(url)}`,
};

/**
 * Checks if a given domain or URL is CORS restricted for client browsers.
 */
export function isCorsRestrictedDomain(url: string, restrictedDomains: string[] = KNOWN_CORS_RESTRICTED_DOMAINS): boolean {
  if (!url) return false;
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    return restrictedDomains.some(d => hostname === d || hostname.endsWith(`.${d}`));
  } catch {
    return false;
  }
}

/**
 * Pings a proxy or server endpoint to verify connectivity.
 */
export async function pingProxy(urlOrTemplate: string, timeoutMs: number = 2500): Promise<{ ok: boolean; status?: number; error?: string }> {
  try {
    let testUrl = urlOrTemplate;
    if (testUrl === 'local' || testUrl.includes('localhost:8000')) {
      testUrl = 'http://localhost:8000/health';
    } else if (testUrl === 'allorigins') {
      testUrl = 'https://api.allorigins.win/raw?url=https%3A%2F%2Ficanhazip.com';
    } else if (testUrl === 'corsproxy') {
      testUrl = 'https://corsproxy.io/?url=https%3A%2F%2Ficanhazip.com';
    } else if (testUrl.includes('{url}')) {
      testUrl = testUrl.replace('{url}', encodeURIComponent('https://icanhazip.com'));
    } else if (testUrl.endsWith('=')) {
      testUrl = `${testUrl}${encodeURIComponent('https://icanhazip.com')}`;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const resp = await fetch(testUrl, { method: 'GET', signal: controller.signal }).catch((err) => {
      throw err;
    });
    clearTimeout(timer);
    return { ok: resp.ok, status: resp.status };
  } catch (err: any) {
    return { ok: false, error: err?.message || 'Connection error' };
  }
}

/**
 * Normalizes remote URLs (e.g. GitHub blob/raw links to raw.githubusercontent.com for CORS compatibility).
 */
export function normalizeResourceUrl(url: string): string {
  if (!url) return url;
  const trimmed = url.trim().replace(/^['"`]|['"`]$/g, '');
  const githubBlobMatch = trimmed.match(/^https?:\/\/(?:www\.)?github\.com\/([^/]+)\/([^/]+)\/(?:blob|raw)\/([^/]+)\/(.+)$/);
  if (githubBlobMatch) {
    const [, user, repo, branch, path] = githubBlobMatch;
    return `https://raw.githubusercontent.com/${user}/${repo}/${branch}/${path}`;
  }
  return trimmed;
}

/**
 * Normalizes manifest resources by unpacking nested resources from container archives (e.g. ZIP files).
 */
export function normalizeManifestResources(rawResources: any[]): DataResource[] {
  if (!Array.isArray(rawResources)) return [];
  const normalized: DataResource[] = [];

  for (const r of rawResources) {
    if (!r || typeof r !== 'object') continue;

    const hasNested = Array.isArray(r.resources) && r.resources.length > 0;

    if (hasNested) {
      for (const inner of r.resources) {
        if (!inner || typeof inner !== 'object') continue;
        const innerPath = inner.path || '';
        const innerFormat = (inner.format || 
          (innerPath.endsWith('.csv') ? 'csv' : 
           innerPath.endsWith('.parquet') ? 'parquet' : 
           innerPath.endsWith('.json') ? 'json' : 
           (r.format && r.format !== 'zip' ? r.format : 'csv'))).toLowerCase();

        const innerName = inner.name || 
          (innerPath ? innerPath.split('/').pop()?.split('\\').pop() : '') || 
          r.name || 
          'recurso';

        normalized.push({
          name: innerName,
          path: inner.path || r.path || '',
          container_path: r.path || undefined,
          container_mediatype: r.mediatype || 'zip',
          format: innerFormat,
          mediatype: inner.mediatype || (innerFormat === 'csv' ? 'text/csv' : undefined),
          schema: inner.schema || undefined,
          policy: inner.policy || r.policy || 'allow_all',
          description: inner.description || r.description || undefined,
        });
      }

      // If the container itself has a name and explicit schema with fields, keep it too
      if (r.name && r.schema?.fields?.length && !normalized.some(nr => nr.name === r.name)) {
        normalized.unshift({
          name: r.name,
          path: r.path || '',
          format: r.format || 'zip',
          mediatype: r.mediatype || 'application/zip',
          schema: r.schema,
          policy: r.policy || 'allow_all',
          description: r.description,
        });
      }
    } else {
      const rPath = r.path || '';
      const rFormat = (r.format || 
        (rPath.endsWith('.csv') ? 'csv' : 
         rPath.endsWith('.parquet') ? 'parquet' : 
         rPath.endsWith('.json') ? 'json' : 
         rPath.endsWith('.zip') ? 'zip' : 'csv')).toLowerCase();

      const rName = r.name || 
        (rPath ? rPath.split('/').pop()?.split('\\').pop() : '') || 
        'recurso';

      normalized.push({
        name: rName,
        path: rPath,
        format: rFormat,
        mediatype: r.mediatype,
        schema: r.schema,
        policy: r.policy || 'allow_all',
        description: r.description,
      });
    }
  }

  return normalized;
}

/**
 * Parses a DataPackage manifest from raw JSON or YAML content.
 * Accepts an optional custom YAML parser callback (e.g. js-yaml) or falls back to
 * JSON parsing and simple structural scanner.
 */
export function parseDataPackageManifest(
  rawContent: string,
  options?: { yamlParser?: (content: string) => any; filePath?: string }
): DataPackage | null {
  if (!rawContent || typeof rawContent !== 'string') return null;
  const trimmed = rawContent.trim();
  if (!trimmed) return null;

  // 1. JSON parsing
  if (trimmed.startsWith('{') || (options?.filePath && options.filePath.endsWith('.json'))) {
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed && typeof parsed === 'object') {
        return {
          name: parsed.name,
          title: parsed.title,
          description: parsed.description,
          spatial: parsed.spatial,
          temporal: parsed.temporal,
          quality: parsed.quality,
          resources: normalizeManifestResources(parsed.resources),
        };
      }
    } catch {
      // Fall through to other parsers
    }
  }

  // 2. Custom YAML parser if injected (e.g. yaml.load in Node or browser)
  if (options?.yamlParser) {
    try {
      const parsed = options.yamlParser(trimmed);
      if (parsed && typeof parsed === 'object') {
        return {
          name: parsed.name,
          title: parsed.title,
          description: parsed.description,
          spatial: parsed.spatial,
          temporal: parsed.temporal,
          quality: parsed.quality,
          resources: normalizeManifestResources(parsed.resources),
        };
      }
    } catch {
      // Fall through to simple scanner
    }
  }

  // 3. Fallback: lightweight scanner
  try {
    const scannedResources = parseSimpleYamlResources(trimmed);
    const titleMatch = trimmed.match(/^title:\s*(.+)$/m);
    const nameMatch = trimmed.match(/^name:\s*(.+)$/m);
    const descMatch = trimmed.match(/^description:\s*(.+)$/m);

    return {
      name: nameMatch ? nameMatch[1].trim().replace(/^['"]|['"]$/g, '') : undefined,
      title: titleMatch ? titleMatch[1].trim().replace(/^['"]|['"]$/g, '') : undefined,
      description: descMatch ? descMatch[1].trim().replace(/^['"]|['"]$/g, '') : undefined,
      resources: scannedResources.map((r) => ({
        name: r.name || '',
        path: r.path || '',
      })),
    };
  } catch {
    return null;
  }
}

/**
 * Lightweight scanner extracting resource definitions from datapackage.yaml/yml text.
 */
export function parseSimpleYamlResources(text: string): Array<{ name?: string; path?: string }> {
  const resources: Array<{ name?: string; path?: string }> = [];
  const lines = text.split('\n');
  let inResources = false;
  let currentRes: { name?: string; path?: string } | null = null;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;

    if (/^resources:\s*$/.test(line) || /^resources:/.test(line)) {
      inResources = true;
      continue;
    }

    if (inResources) {
      if (/^[a-zA-Z0-9_-]+:/.test(line) && !line.startsWith('-') && !rawLine.startsWith(' ') && !rawLine.startsWith('\t')) {
        if (currentRes) {
          resources.push(currentRes);
          currentRes = null;
        }
        break;
      }

      if (line.startsWith('-')) {
        if (currentRes) {
          resources.push(currentRes);
        }
        currentRes = {};
        const content = line.replace(/^-\s*/, '').trim();
        const colonIdx = content.indexOf(':');
        if (colonIdx > 0) {
          const key = content.substring(0, colonIdx).trim();
          const val = content.substring(colonIdx + 1).trim().replace(/^['"]|['"]$/g, '');
          if (key === 'name') currentRes.name = val;
          else if (key === 'path') currentRes.path = val;
        }
      } else if (currentRes) {
        const colonIdx = line.indexOf(':');
        if (colonIdx > 0) {
          const key = line.substring(0, colonIdx).trim();
          const val = line.substring(colonIdx + 1).trim().replace(/^['"]|['"]$/g, '');
          if (key === 'name') currentRes.name = val;
          else if (key === 'path') currentRes.path = val;
        }
      }
    }
  }

  if (currentRes) {
    resources.push(currentRes);
  }

  return resources;
}

/**
 * Parses any canonical triad, datamesh:// URI, URL, or table identifier into a structured ResourceTriad.
 * Supports:
 * - 'catalogo:dataset:resource' (3 parts)
 * - 'dataset:resource' (2 parts)
 * - 'catalogo/dataset/recurso' (3 parts)
 * - 'dataset/recurso' (2 parts)
 * - 'https://.../datasets/cartera-creditos/creditos.csv'
 * - 'datamesh://catalogo/dataset/resource'
 * - 'datamesh://dataset/resource'
 */
export function parseCanonicalUri(raw: string): ResourceTriad | null {
  const trimmed = raw.trim().replace(/^['"`]|['"`]$/g, '');
  if (!trimmed) return null;

  // 1. datamesh:// or odkf:// scheme
  if (trimmed.startsWith("datamesh://") || trimmed.startsWith("odkf://")) {
    const clean = trimmed.split("://")[1];
    const parts = clean.split("/").map((p) => p.trim()).filter(Boolean);
    if (parts.length >= 3) {
      return { catalog: parts[0], dataset: parts[1], resource: parts[2] };
    } else if (parts.length === 2) {
      return { dataset: parts[0], resource: parts[1] };
    }
    return null;
  }

  // 2. HTTP/HTTPS or file URLs (e.g. https://.../datasets/cartera-creditos/creditos.csv)
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://") || trimmed.startsWith("file://")) {
    const cleanUrl = trimmed.split("?")[0].split("#")[0].replace(/\/+$/, '');
    const urlParts = cleanUrl.split("/").filter(Boolean);
    if (urlParts.length >= 2) {
      const ds = urlParts[urlParts.length - 2];
      const resRaw = urlParts[urlParts.length - 1];
      const res = resRaw.includes(".") ? resRaw.substring(0, resRaw.lastIndexOf(".")) : resRaw;
      if (ds && res) {
        return { dataset: ds, resource: res };
      }
    }
  }

  // 3. Colon-separated format ('cat:ds:res' or 'ds:res')
  if (trimmed.includes(":") && !trimmed.startsWith("http://") && !trimmed.startsWith("https://") && !trimmed.startsWith("file://")) {
    const parts = trimmed.split(":");
    if (parts.length === 3) {
      const cat = parts[0].trim();
      const ds = parts[1].trim();
      const res = parts[2].trim();
      if (ds && res) {
        return { catalog: cat || undefined, dataset: ds, resource: res };
      }
    } else if (parts.length === 2) {
      const ds = parts[0].trim();
      const res = parts[1].trim();
      if (ds && res) {
        return { dataset: ds, resource: res };
      }
    }
  }

  // 4. Slash-separated format ('cat/ds/res' or 'ds/res')
  if (trimmed.includes("/")) {
    const parts = trimmed.split("/").map((p) => p.trim()).filter(Boolean);
    if (parts.length === 3) {
      return { catalog: parts[0], dataset: parts[1], resource: parts[2] };
    } else if (parts.length === 2) {
      return { dataset: parts[0], resource: parts[1] };
    }
  }

  return null;
}

/**
 * Formats a ResourceTriad into canonical 'dataset:resource' or 'catalog:dataset:resource' string.
 */
export function toCanonicalTriad(triad: ResourceTriad): string {
  if (triad.catalog) {
    return `${triad.catalog}:${triad.dataset}:${triad.resource}`;
  }
  return `${triad.dataset}:${triad.resource}`;
}

/**
 * Formats a ResourceTriad into sovereign 'datamesh://...' URI.
 */
export function toCanonicalUri(triad: ResourceTriad): string {
  if (triad.catalog) {
    return `datamesh://${triad.catalog}/${triad.dataset}/${triad.resource}`;
  }
  return `datamesh://${triad.dataset}/${triad.resource}`;
}

/**
 * Returns the default catalog endpoint.
 * In a web browser, resolves to the current host's /llms.txt.
 * In headless/Node environments, defaults to the canonical Datos Bolivia catalog.
 */
export function getDefaultCatalogUrl(): string {
  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin}/llms.txt`;
  }
  return "https://datosbolivia.github.io/llms.txt";
}

/**
 * Parses raw CSV/TSV text into column headers and rows, safely respecting quotes and multiline values.
 */
export function parseCsv(text: string, delimiter?: string): { columns: string[]; rows: string[][] } {
  const clean = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (!clean.trim()) {
    return { columns: [], rows: [] };
  }

  const delim = delimiter || (clean.split("\n")[0].includes("\t") ? "\t" : ",");

  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentField = "";
  let inQuotes = false;

  for (let i = 0; i < clean.length; i++) {
    const char = clean[i];
    const nextChar = clean[i + 1];

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        currentField += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === delim && !inQuotes) {
      currentRow.push(currentField.trim());
      currentField = "";
    } else if (char === "\n" && !inQuotes) {
      currentRow.push(currentField.trim());
      if (currentRow.some((f) => f.length > 0)) {
        rows.push(currentRow);
      }
      currentRow = [];
      currentField = "";
    } else {
      currentField += char;
    }
  }

  if (currentField || currentRow.length > 0) {
    currentRow.push(currentField.trim());
    if (currentRow.some((f) => f.length > 0)) {
      rows.push(currentRow);
    }
  }

  if (rows.length === 0) {
    return { columns: [], rows: [] };
  }

  return {
    columns: rows[0],
    rows: rows.slice(1),
  };
}

/**
 * DuckDB WASM Client Engine for Browser execution.
 * Lazily loads DuckDB-WASM via dynamic import and executes full ANSI SQL.
 */
export class DuckDBBrowserEngine {
  private db: any = null;
  private conn: any = null;
  private initPromise: Promise<boolean> | null = null;
  private registeredViews: Set<string> = new Set();

  async init(): Promise<boolean> {
    if (this.conn) return true;
    if (this.initPromise) return this.initPromise;

    this.initPromise = (async () => {
      if (typeof window === "undefined") {
        return false;
      }
      try {
        const duckdbUrl = "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.28.0/+esm";
        const duckdb: any = await (Function("url", "return import(url)")(duckdbUrl));
        const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
        const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);
        const workerBlob = new Blob([`importScripts("${bundle.mainWorker}");`], { type: "text/javascript" });
        const workerUrl = URL.createObjectURL(workerBlob);
        const worker = new Worker(workerUrl);
        const logger = new duckdb.ConsoleLogger();
        const db = new duckdb.AsyncDuckDB(logger, worker);
        await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
        URL.revokeObjectURL(workerUrl);
        this.db = db;
        this.conn = await db.connect();
        return true;
      } catch (err) {
        console.warn("[DataMeshClient] DuckDB-WASM unavailable, falling back to in-memory engine:", err);
        this.db = null;
        this.conn = null;
        return false;
      }
    })();

    return this.initPromise;
  }

  async executeSql(
    sqlQuery: string,
    fileRegistrations?: Record<string, string>
  ): Promise<QueryResult | null> {
    const ready = await this.init();
    if (!ready || !this.conn) return null;

    try {
      if (fileRegistrations && this.db) {
        for (const [name, contentOrUrl] of Object.entries(fileRegistrations)) {
          try {
            if (contentOrUrl.startsWith("http://") || contentOrUrl.startsWith("https://") || contentOrUrl.startsWith("/")) {
              await this.db.registerFileURL(name, contentOrUrl, 4, false);
            } else {
              await this.db.registerFileText(name, contentOrUrl);
            }
            // Register views under name and slugified identifier
            if (!this.registeredViews.has(name)) {
              try {
                await this.conn.query(`CREATE OR REPLACE VIEW "${name}" AS SELECT * FROM '${name}'`);
                this.registeredViews.add(name);
                const slugName = slugify(name);
                if (slugName && !this.registeredViews.has(slugName)) {
                  await this.conn.query(`CREATE OR REPLACE VIEW "${slugName}" AS SELECT * FROM '${name}'`);
                  this.registeredViews.add(slugName);
                }
              } catch {
                // view creation fallback
              }
            }
          } catch {
            // view registration retry
          }
        }
      }

      const arrowTable = await this.conn.query(sqlQuery);
      const columns: string[] = arrowTable.schema.fields.map((f: any) => f.name);
      const rows: string[][] = [];

      for (let i = 0; i < arrowTable.numRows; i++) {
        const row: string[] = [];
        for (const col of columns) {
          const val = arrowTable.getChild(col)?.get(i);
          row.push(val !== null && val !== undefined ? String(val) : "");
        }
        rows.push(row);
      }

      return {
        columns,
        rows,
        row_count: rows.length,
        total_count: rows.length,
        engine: "duckdb-wasm",
      };
    } catch (err) {
      console.warn("[DataMeshClient] DuckDB query error, falling back:", err);
      return null;
    }
  }
}

/**
 * DataMesh Sovereign Client SDK in TypeScript.
 * Provides client-side catalog federation, direct HTTP tabular streaming, and in-memory/DuckDB SQL querying.
 */
export class DataMeshClient {
  private catalogUrls: string[];
  public engine: ExecutionEngine;
  public proxyUrl?: string;
  private duckdbEngine: DuckDBBrowserEngine;
  private catalogCache: Catalog | null = null;

  public defaultDataset?: string;
  public defaultResources?: Array<{ name?: string; path?: string; [key: string]: any }>;

  constructor(options: DataMeshClientOptions | string[] = {}) {
    if (Array.isArray(options)) {
      this.catalogUrls = options.length > 0 ? options : [getDefaultCatalogUrl()];
      this.engine = "duckdb";
    } else {
      this.catalogUrls = options.catalogUrls && options.catalogUrls.length > 0
        ? options.catalogUrls
        : [getDefaultCatalogUrl()];
      this.engine = options.engine || "duckdb";
      this.proxyUrl = options.proxyUrl;
      this.defaultDataset = options.defaultDataset;
      this.defaultResources = options.defaultResources;
    }
    this.duckdbEngine = new DuckDBBrowserEngine();
  }

  /**
   * Sets or updates the active CORS proxy URL or template.
   * e.g. "https://api.allorigins.win/raw?url={url}" or "https://corsproxy.io/?url={url}"
   */
  setProxy(proxyUrl?: string): void {
    this.proxyUrl = proxyUrl;
  }

  /**
   * Formats a target URL through the configured proxy.
   */
  formatProxiedUrl(targetUrl: string, customProxy?: string): string {
    const proxy = customProxy || this.proxyUrl;
    if (!proxy || !targetUrl) return targetUrl;
    if (proxy.includes('{url}')) {
      return proxy.replace('{url}', encodeURIComponent(targetUrl));
    }
    if (proxy.endsWith('=') || proxy.endsWith('?url=')) {
      return `${proxy}${encodeURIComponent(targetUrl)}`;
    }
    const sep = proxy.includes('?') ? '&' : '?';
    return `${proxy}${sep}url=${encodeURIComponent(targetUrl)}`;
  }

  /**
   * Resolves any canonical triad ('ds:res', 'cat:ds:res'), sovereign URI ('datamesh://...'),
   * or direct URL into a physical fetchable URL.
   */
  async resolveResource(uriOrTriad: string, context?: DatasetContext): Promise<string> {
    const trimmed = uriOrTriad.trim().replace(/^['"`]|['"`]$/g, '');
    if (
      trimmed.startsWith("http://") ||
      trimmed.startsWith("https://") ||
      trimmed.startsWith("file://") ||
      trimmed.startsWith("/")
    ) {
      return normalizeResourceUrl(trimmed);
    }

    const activeResources = context?.resources || this.defaultResources;
    const activeDataset = context?.dataset || context?.slug || this.defaultDataset;

    // Check if matching resource is present in scoped resources
    if (activeResources && activeResources.length > 0) {
      const cleanTarget = trimmed.toLowerCase();
      const matched = activeResources.find((r) => {
        const rName = String(r.name || "").toLowerCase();
        const rPath = String(r.path || "").toLowerCase();
        return (
          rName === cleanTarget ||
          slugify(rName) === slugify(cleanTarget) ||
          rPath === cleanTarget ||
          rPath.endsWith(`/${cleanTarget}`) ||
          rPath.endsWith(`\\${cleanTarget}`)
        );
      });
      if (matched && matched.path) {
        return normalizeResourceUrl(matched.path);
      }
    }

    let parsed = parseCanonicalUri(trimmed);
    if (!parsed && activeDataset && !trimmed.includes(':') && !trimmed.includes('/')) {
      parsed = { dataset: activeDataset, resource: trimmed };
    }

    if (!parsed) {
      return normalizeResourceUrl(trimmed);
    }

    const { dataset, resource } = parsed;
    const cleanDs = dataset.toLowerCase();
    const cleanRes = resource.toLowerCase();
    const resSlug = slugify(resource);

    // 1. Discover catalog entries
    const cat = await this.discover();
    const matchedEntry = cat.entries.find((e) => {
      const u = e.uri.toLowerCase();
      const r = (e.resolved_url || "").toLowerCase();
      const t = e.title.toLowerCase();
      return u.includes(cleanDs) || r.includes(cleanDs) || t === cleanDs || slugify(t) === slugify(cleanDs);
    });

    if (matchedEntry && matchedEntry.resolved_url) {
      const baseDir = matchedEntry.resolved_url.substring(0, matchedEntry.resolved_url.lastIndexOf('/'));

      // 2. Try fetching datapackage (json or yaml/yml) at baseDir
      const dpCandidates = [
        `${baseDir}/datapackage.json`,
        `${baseDir}/datapackage.yaml`,
        `${baseDir}/datapackage.yml`
      ];

      for (const dpUrl of dpCandidates) {
        try {
          const resp = await fetch(dpUrl);
          if (resp.ok) {
            let resList: Array<{ name?: string; path?: string }> = [];
            if (dpUrl.endsWith('.json')) {
              const pkg = await resp.json();
              if (pkg.resources && Array.isArray(pkg.resources)) {
                resList = pkg.resources;
              }
            } else {
              const text = await resp.text();
              resList = parseSimpleYamlResources(text);
            }

            if (resList.length > 0) {
              const foundRes = resList.find((r: any) => {
                const rName = String(r.name || "").toLowerCase();
                return rName === cleanRes || slugify(rName) === resSlug || rName.includes(resSlug);
              });
              if (foundRes && foundRes.path) {
                const normPath = normalizeResourceUrl(foundRes.path);
                if (normPath.startsWith("http://") || normPath.startsWith("https://")) {
                  return normPath;
                }
                return new URL(normPath, `${baseDir}/`).toString();
              }
            }
          }
        } catch {
          // continue fallback
        }
      }

      // 3. Fallback to direct file inside node directory
      return `${baseDir}/${resource}.csv`;
    }

    return normalizeResourceUrl(trimmed);
  }

  /**
   * Discovers sovereign data products across configured federated catalogs or a specified endpoint.
   * Leverages Go Core WASM runtime (window.DataMesh) when loaded, with pure JS fallback.
   */
  async discover(url?: string): Promise<Catalog> {
    if (typeof window !== "undefined" && (window as any).DataMesh?.discover) {
      try {
        const cat = await (window as any).DataMesh.discover(url || "");
        if (cat && cat.entries) return cat;
      } catch {
        // Fallback to pure TS client
      }
    }

    const targets = url ? [url] : this.catalogUrls;

    if (!url && this.catalogCache && targets.length === this.catalogUrls.length) {
      return this.catalogCache;
    }

    if (targets.length === 1) {
      const single = await this.fetchSingleCatalog(targets[0]);
      if (!url) this.catalogCache = single;
      return single;
    }

    const combinedEntries: CatalogEntry[] = [];
    const sourceCatalogs: string[] = [];
    const seen = new Set<string>();

    await Promise.all(
      targets.map(async (target) => {
        try {
          const cat = await this.fetchSingleCatalog(target);
          sourceCatalogs.push(target);
          for (const entry of cat.entries) {
            entry.catalog_source = target;
            const key = entry.resolved_url || entry.title;
            if (!seen.has(key)) {
              seen.add(key);
              combinedEntries.push(entry);
            }
          }
        } catch {
          // resilient discovery: keep remaining catalogs
        }
      })
    );

    const result: Catalog = {
      title: "DataMesh Federated Catalog",
      description: "Aggregated decentralized sovereign data products",
      source_catalogs: sourceCatalogs,
      entries: combinedEntries,
    };

    if (!url) this.catalogCache = result;
    return result;
  }

  /**
   * Searches entries across sovereign catalogs matching title, description, or domain.
   * Leverages Go Core WASM runtime (window.DataMesh) when loaded, with pure JS fallback.
   */
  async search(keyword: string, url?: string): Promise<CatalogEntry[]> {
    if (typeof window !== "undefined" && (window as any).DataMesh?.search) {
      try {
        const entries = await (window as any).DataMesh.search(keyword, url || "");
        if (entries && Array.isArray(entries)) return entries;
      } catch {
        // Fallback
      }
    }

    const cat = await this.discover(url);
    const kw = keyword.toLowerCase();
    return cat.entries.filter(
      (e) =>
        e.title.toLowerCase().includes(kw) ||
        e.description.toLowerCase().includes(kw) ||
        e.domain.toLowerCase().includes(kw)
    );
  }

  /**
   * Resolves an OKF v0.2 Data Product manifest, description, and resources from a node URI or URL.
   * Leverages Go Core WASM runtime (window.DataMesh) when loaded, with pure JS fallback.
   */
  async get(uriOrUrl: string): Promise<DataProduct> {
    if (typeof window !== "undefined" && ((window as any).DataMesh?.get || (window as any).DataMesh?.resolve)) {
      try {
        const fn = (window as any).DataMesh.get || (window as any).DataMesh.resolve;
        const dp = await fn(uriOrUrl);
        if (dp && dp.manifest) return dp;
      } catch {
        // Fallback
      }
    }

    const trimmed = uriOrUrl.trim().replace(/^['"`]|['"`]$/g, '');
    let targetUrl = trimmed;

    // Check if it's already a direct HTTP URL to index.md or a directory
    if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://") && !targetUrl.startsWith("file://")) {
      const parsed = parseCanonicalUri(trimmed);
      const ds = parsed ? parsed.dataset : trimmed.split(":")[0];
      const cat = await this.discover();
      const matched = cat.entries.find((e) => {
        const u = e.uri.toLowerCase();
        const r = (e.resolved_url || "").toLowerCase();
        const t = e.title.toLowerCase();
        return u.includes(ds.toLowerCase()) || r.includes(ds.toLowerCase()) || t === ds.toLowerCase();
      });
      if (matched && matched.resolved_url) {
        targetUrl = matched.resolved_url;
      }
    }

    if (targetUrl.endsWith('/')) {
      targetUrl += 'index.md';
    } else if (!targetUrl.endsWith('.md') && !targetUrl.endsWith('.yaml') && !targetUrl.endsWith('.json')) {
      targetUrl += '/index.md';
    }

    if (this.proxyUrl) {
      targetUrl = this.formatProxiedUrl(targetUrl);
    }

    const resp = await fetch(targetUrl);
    if (!resp.ok) {
      throw new Error(`Failed to resolve Data Product from '${targetUrl}': HTTP ${resp.status}`);
    }
    const text = await resp.text();

    let manifest: Manifest = {
      type: "dataset",
      title: trimmed,
      dimensions: [],
      lineage: { version: "1.0.0" }
    };
    let description = "";

    if (text.startsWith("---")) {
      const parts = text.split("---");
      if (parts.length >= 3) {
        description = parts.slice(2).join("---").trim();
        const frontLines = parts[1].split("\n");
        for (const line of frontLines) {
          const l = line.trim();
          if (l.startsWith("title:")) manifest.title = l.substring(6).trim().replace(/^['"]|['"]$/g, '');
          else if (l.startsWith("type:")) manifest.type = l.substring(5).trim().replace(/^['"]|['"]$/g, '');
        }
      }
    } else {
      description = text;
    }

    return {
      id: trimmed,
      manifest,
      description,
      raw_content: text
    };
  }

  /**
   * Fetches and queries a tabular resource directly from the browser/client.
   * Supports canonical triad URIs (e.g. 'dataset:resource') or direct HTTP URLs.
   * Leverages Go Core WASM runtime (window.DataMesh) when loaded, with pure JS fallback.
   */
  async query(req: QueryRequest, context?: DatasetContext): Promise<QueryResult> {
    if (!req.resource_uri) {
      throw new Error("QueryRequest requires a 'resource_uri'");
    }

    if (typeof window !== "undefined" && (window as any).DataMesh?.query) {
      try {
        const qRes = await (window as any).DataMesh.query(req.resource_uri, JSON.stringify(req));
        if (qRes && qRes.columns) return qRes;
      } catch {
        // Fallback
      }
    }

    // Resolves canonical URI ('air_quality:mediciones', 'datamesh://...', or direct URL)
    let resolvedUrl = await this.resolveResource(req.resource_uri, context);
    if (req.proxy_url || this.proxyUrl) {
      resolvedUrl = this.formatProxiedUrl(resolvedUrl, req.proxy_url);
    }

    const res = await fetch(resolvedUrl);
    if (!res.ok) {
      throw new Error(`Failed to fetch tabular resource from '${resolvedUrl}' (resolved from '${req.resource_uri}'): HTTP ${res.status}`);
    }

    const text = await res.text();
    const parsed = parseCsv(text);
    return this.queryTable(parsed, req);
  }

  /**
   * Runs in-memory filtering, keyword search, sorting, and pagination on parsed tabular data.
   */
  queryTable(
    table: { columns: string[]; rows: string[][] },
    req: Omit<QueryRequest, "resource_uri">
  ): QueryResult {
    const { columns, rows } = table;
    const colMap: Record<string, number> = {};
    columns.forEach((col, idx) => {
      colMap[col.toLowerCase()] = idx;
    });

    let filtered = [...rows];

    // 1. Column equality filters
    if (req.filters) {
      for (const [k, v] of Object.entries(req.filters)) {
        const idx = colMap[k.toLowerCase().trim()];
        if (idx !== undefined) {
          const target = v.toLowerCase().trim();
          filtered = filtered.filter((row) => (row[idx] || "").toLowerCase().trim() === target);
        }
      }
    }

    // 2. Global keyword search
    if (req.search) {
      const q = req.search.toLowerCase().trim();
      filtered = filtered.filter((row) =>
        row.some((cell) => (cell || "").toLowerCase().includes(q))
      );
    }

    // 3. Column sorting
    if (req.sort_by) {
      const sortIdx = colMap[req.sort_by.toLowerCase().trim()];
      if (sortIdx !== undefined) {
        const direction = req.sort_direction === "desc" ? -1 : 1;
        filtered.sort((a, b) => {
          const valA = a[sortIdx] || "";
          const valB = b[sortIdx] || "";
          const numA = parseFloat(valA);
          const numB = parseFloat(valB);
          if (!isNaN(numA) && !isNaN(numB)) {
            return (numA - numB) * direction;
          }
          return valA.localeCompare(valB, undefined, { numeric: true }) * direction;
        });
      }
    }

    const totalCount = filtered.length;
    const offset = req.offset && req.offset > 0 ? req.offset : 0;
    const limit = req.limit && req.limit > 0 ? req.limit : totalCount;

    const pagedRows = filtered.slice(offset, offset + limit);

    return {
      columns,
      rows: pagedRows,
      row_count: pagedRows.length,
      total_count: totalCount,
      engine: "in-memory",
    };
  }

  /**
   * Executes SQL against a remote resource, in-memory table, or canonical triad references.
   * If engine is 'duckdb', attempts execution via DuckDB-WASM with fallback to in-memory engine.
   */
  async sql(
    sqlQuery: string,
    sourceOrOptions?: string | { columns: string[]; rows: string[][] } | Record<string, string>,
    tableAlias: string = "resource"
  ): Promise<QueryResult> {
    // 1. Direct table object passed
    if (sourceOrOptions && typeof sourceOrOptions === "object" && "columns" in sourceOrOptions) {
      return this.executeWithDirectSource(sqlQuery, sourceOrOptions as { columns: string[]; rows: string[][] }, tableAlias);
    }

    // 2. Direct single URL string passed with table alias
    if (
      typeof sourceOrOptions === "string" &&
      (sourceOrOptions.startsWith("http://") || sourceOrOptions.startsWith("https://") || sourceOrOptions.startsWith("/"))
    ) {
      return this.executeWithDirectSource(sqlQuery, sourceOrOptions, tableAlias);
    }

    const tableMapping: Record<string, string> =
      sourceOrOptions && typeof sourceOrOptions === "object" && !("columns" in sourceOrOptions)
        ? (sourceOrOptions as Record<string, string>)
        : {};

    // 3. Extract table references from SQL query
    const tableRefs: string[] = [];
    const fromMatches = Array.from(sqlQuery.matchAll(TABLE_REF_PATTERN));
    for (const m of fromMatches) {
      const ref = (m[1] || m[2] || "").trim();
      if (ref && !tableRefs.includes(ref)) {
        tableRefs.push(ref);
      }
    }
    const quotedMatches = Array.from(sqlQuery.matchAll(QUOTED_COLON_PATTERN));
    for (const m of quotedMatches) {
      const ref = (m[1] || "").trim();
      if (ref && !tableRefs.includes(ref)) {
        tableRefs.push(ref);
      }
    }
    const quotedSlashMatches = Array.from(sqlQuery.matchAll(QUOTED_SLASH_PATTERN));
    for (const m of quotedSlashMatches) {
      const ref = (m[1] || "").trim();
      if (ref && !tableRefs.includes(ref)) {
        tableRefs.push(ref);
      }
    }

    // 4. Resolve physical URLs for each table reference
    const resolvedTableUrls: Record<string, string> = {};
    for (const ref of tableRefs) {
      if (tableMapping[ref]) {
        resolvedTableUrls[ref] = tableMapping[ref];
      } else {
        const resolved = await this.resolveResource(ref);
        resolvedTableUrls[ref] = resolved;
      }
    }

    // 5. DuckDB Execution
    if (this.engine === "duckdb") {
      const fileRegistrations: Record<string, string> = {};
      for (const [ref, url] of Object.entries(resolvedTableUrls)) {
        fileRegistrations[ref] = url;
        const clean = slugify(ref);
        if (clean) fileRegistrations[clean] = url;
      }

      const duckResult = await this.duckdbEngine.executeSql(sqlQuery, fileRegistrations);
      if (duckResult) {
        return duckResult;
      }
    }

    // 6. In-Memory Execution fallback (single table query)
    const primaryRef = tableRefs[0];
    const primaryUrl = primaryRef ? resolvedTableUrls[primaryRef] : Object.values(tableMapping)[0];
    if (!primaryUrl) {
      throw new Error(`Could not resolve any table reference from SQL query: ${sqlQuery}`);
    }

    const res = await fetch(primaryUrl);
    if (!res.ok) {
      throw new Error(`Failed to fetch tabular resource from '${primaryUrl}': HTTP ${res.status}`);
    }
    const text = await res.text();
    const table = parseCsv(text);

    return this.queryTableWithSql(table, sqlQuery);
  }

  private async executeWithDirectSource(
    sqlQuery: string,
    source: string | { columns: string[]; rows: string[][] },
    tableAlias: string
  ): Promise<QueryResult> {
    if (this.engine === "duckdb") {
      let dataContent: string;
      if (typeof source === "string") {
        dataContent = normalizeResourceUrl(source);
      } else {
        let csvStr = source.columns.map((c) => `"${c.replace(/"/g, '""')}"`).join(",") + "\n";
        source.rows.forEach((r) => {
          csvStr += r.map((c) => `"${(c || "").replace(/"/g, '""')}"`).join(",") + "\n";
        });
        dataContent = csvStr;
      }

      const fileRegistrations: Record<string, string> = {
        [tableAlias]: dataContent,
        resource: dataContent,
      };
      const sAlias = slugify(tableAlias);
      if (sAlias) fileRegistrations[sAlias] = dataContent;

      const fromMatches = Array.from(sqlQuery.matchAll(TABLE_REF_PATTERN));
      for (const m of fromMatches) {
        const ref = (m[1] || m[2] || "").trim();
        if (ref) {
          fileRegistrations[ref] = dataContent;
          const s = slugify(ref);
          if (s) fileRegistrations[s] = dataContent;
        }
      }
      const quotedMatches = Array.from(sqlQuery.matchAll(QUOTED_COLON_PATTERN));
      for (const m of quotedMatches) {
        const ref = (m[1] || "").trim();
        if (ref) {
          fileRegistrations[ref] = dataContent;
          const s = slugify(ref);
          if (s) fileRegistrations[s] = dataContent;
        }
      }

      const duckResult = await this.duckdbEngine.executeSql(sqlQuery, fileRegistrations);
      if (duckResult) {
        return duckResult;
      }
    }

    let table: { columns: string[]; rows: string[][] };
    if (typeof source === "string") {
      const res = await fetch(source);
      if (!res.ok) {
        throw new Error(`Failed to fetch tabular resource: HTTP ${res.status}`);
      }
      const text = await res.text();
      table = parseCsv(text);
    } else {
      table = source;
    }

    return this.queryTableWithSql(table, sqlQuery);
  }

  private queryTableWithSql(
    table: { columns: string[]; rows: string[][] },
    sqlQuery: string
  ): QueryResult {
    const normalizedSql = sqlQuery.trim();

    // Extract LIMIT and OFFSET
    let limit: number | undefined;
    let offset: number | undefined;
    const limitMatch = normalizedSql.match(/\bLIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?/i);
    if (limitMatch) {
      limit = parseInt(limitMatch[1], 10);
      if (limitMatch[2]) {
        offset = parseInt(limitMatch[2], 10);
      }
    }

    // Extract ORDER BY
    let sortBy: string | undefined;
    let sortDir: "asc" | "desc" = "asc";
    const orderMatch = normalizedSql.match(/\bORDER\s+BY\s+([a-zA-Z0-9_]+)(?:\s+(ASC|DESC))?/i);
    if (orderMatch) {
      sortBy = orderMatch[1];
      if (orderMatch[2] && orderMatch[2].toUpperCase() === "DESC") {
        sortDir = "desc";
      }
    }

    // Extract WHERE filters
    const filters: Record<string, string> = {};
    let search: string | undefined;
    const whereMatch = normalizedSql.match(/\bWHERE\s+([\s\S]+?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT|$)/i);
    if (whereMatch) {
      const whereClause = whereMatch[1].trim();
      const eqMatches = whereClause.matchAll(/([a-zA-Z0-9_]+)\s*=\s*['"]?([^'"\s]+)['"]?/gi);
      for (const m of eqMatches) {
        filters[m[1]] = m[2];
      }

      const likeMatch = whereClause.match(/([a-zA-Z0-9_]+)\s+LIKE\s+['"]%?([^%'"\s]+)%?['"]/i);
      if (likeMatch) {
        search = likeMatch[2];
      }
    }

    const queryRes = this.queryTable(table, {
      filters,
      search,
      sort_by: sortBy,
      sort_direction: sortDir,
      limit,
      offset,
    });

    // Extract SELECT column projections
    const selectMatch = normalizedSql.match(/^SELECT\s+([\s\S]+?)\s+FROM/i);
    if (selectMatch && !selectMatch[1].includes("*")) {
      const requestedCols = selectMatch[1]
        .split(",")
        .map((c) => c.trim().replace(/^['"`]|['"`]$/g, ""))
        .filter(Boolean);

      const colIndices: number[] = [];
      const outCols: string[] = [];

      requestedCols.forEach((reqCol) => {
        const cleanCol = reqCol.split(/\s+AS\s+/i)[0].trim().toLowerCase();
        const alias = (reqCol.split(/\s+AS\s+/i)[1] || reqCol).trim();
        const foundIdx = queryRes.columns.findIndex((c) => c.toLowerCase() === cleanCol);
        if (foundIdx >= 0) {
          colIndices.push(foundIdx);
          outCols.push(alias);
        }
      });

      if (colIndices.length > 0) {
        const projectedRows = queryRes.rows.map((r) => colIndices.map((idx) => r[idx] || ""));
        return {
          columns: outCols,
          rows: projectedRows,
          row_count: projectedRows.length,
          total_count: queryRes.total_count,
          engine: "in-memory",
        };
      }
    }

    return queryRes;
  }

  private async fetchSingleCatalog(target: string): Promise<Catalog> {
    const res = await fetch(target);
    if (!res.ok) {
      throw new Error(`Failed to fetch catalog: HTTP ${res.status}`);
    }
    const text = await res.text();
    return this.parseLLMSTxt(text, target);
  }

  private parseLLMSTxt(content: string, sourceUrl: string): Catalog {
    const lines = content.split("\n");
    let title = "";
    let description = "";
    const entries: CatalogEntry[] = [];

    const entryRegex = /^-\s*\[(.*?)\]\((.*?)\)(?::\s*(.*))?$/;
    const domainRegex = /\(Dominio:\s*([^)]*?)(?:\.|\)|Recursos:)/;

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;

      if (line.startsWith("# ") && !title) {
        title = line.substring(2).trim();
        continue;
      }
      if (line.startsWith("> ") && !description) {
        description = line.substring(2).trim();
        continue;
      }

      const match = entryRegex.exec(line);
      if (match) {
        const itemTitle = match[1].trim();
        const rawUri = match[2].trim();
        const descText = match[3] ? match[3].trim() : "";

        let resolvedUrl = rawUri;
        try {
          resolvedUrl = new URL(rawUri, sourceUrl).toString();
        } catch {
          resolvedUrl = rawUri;
        }

        let domainName = "";
        const dMatch = domainRegex.exec(descText);
        if (dMatch) {
          domainName = dMatch[1].trim();
        }

        const cleanDesc = descText.split("(Dominio:")[0].trim();

        entries.push({
          title: itemTitle,
          uri: rawUri,
          resolved_url: resolvedUrl,
          description: cleanDesc,
          domain: domainName,
          catalog_source: sourceUrl,
        });
      }
    }

    return {
      title,
      description,
      source_url: sourceUrl,
      entries,
    };
  }

  async validate(target: string): Promise<ValidationReport> {
    if (typeof window !== "undefined" && (window as any).DataMesh?.validate) {
      try {
        return await (window as any).DataMesh.validate(target);
      } catch (e) {
        console.warn("WASM validate failed, falling back to JS", e);
      }
    }
    const clean = target.trim().replace(/^["']|["']$/g, "");
    const isTriad = /^[a-zA-Z0-9_\-\.]+[:/][a-zA-Z0-9_\-\. ]+([:/][a-zA-Z0-9_\-\. ]+)?$/.test(clean);
    return {
      valid: isTriad,
      target,
      total_errors: isTriad ? 0 : 1,
      total_warnings: 0,
      issues: isTriad ? [] : [{ code: "RULE-08-TRIAD-SYNTAX", severity: "ERROR", message: `Invalid syntax for triad '${target}'` }],
    };
  }
}

/**
 * Universal hook / factory function for initializing DataMesh client in web applications.
 */
export function useDataMesh(options?: DataMeshClientOptions): DataMeshClient {
  return new DataMeshClient(options);
}

export const datamesh = new DataMeshClient();

// Standalone 1-line unified functions matching Python dm.discover, dm.search, dm.get, dm.query, dm.sql, dm.validate
export const discover = (url?: string) => datamesh.discover(url);
export const search = (keyword: string, url?: string) => datamesh.search(keyword, url);
export const get = (uriOrUrl: string) => datamesh.get(uriOrUrl);
export const query = (req: QueryRequest, context?: DatasetContext) => datamesh.query(req, context);
export const sql = (
  sqlQuery: string,
  sourceOrOptions?: string | { columns: string[]; rows: string[][] } | Record<string, string>,
  tableAlias?: string
) => datamesh.sql(sqlQuery, sourceOrOptions, tableAlias);
export const validate = (target: string) => datamesh.validate(target);

/**
 * Configuration options for DataMesh MCP Client.
 */
export interface McpServerConfig {
  serverUrl: string;
  timeoutMs?: number;
  headers?: Record<string, string>;
}

/**
 * Standard client for interacting with DataMesh MCP / JSON-RPC servers.
 */
export class DataMeshMcpClient {
  private serverUrl: string;
  private timeoutMs: number;
  private headers: Record<string, string>;
  private requestId: number = 1;

  constructor(config?: Partial<McpServerConfig>) {
    this.serverUrl = config?.serverUrl || 'http://localhost:8000/mcp';
    this.timeoutMs = config?.timeoutMs || 30000;
    this.headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/event-stream',
      ...(config?.headers || {}),
    };
  }

  setServerUrl(url: string) {
    this.serverUrl = url;
  }

  async ping(): Promise<boolean> {
    try {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), 3000);
      const res = await fetch(`${this.serverUrl.replace(/\/mcp$/, '')}/health`, {
        method: 'GET',
        signal: controller.signal,
      }).catch(() => null);
      clearTimeout(id);
      if (res && res.ok) return true;

      const rpcRes = await this.callRpc('ping', {}, 3000).catch(() => null);
      return Boolean(rpcRes);
    } catch {
      return false;
    }
  }

  async callRpc(method: string, params: Record<string, any> = {}, customTimeout?: number): Promise<any> {
    const id = this.requestId++;
    const payload = {
      jsonrpc: '2.0',
      id,
      method,
      params,
    };

    const controller = new AbortController();
    const timeout = customTimeout || this.timeoutMs;
    const timer = setTimeout(() => controller.abort(), timeout);

    try {
      const res = await fetch(this.serverUrl, {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      clearTimeout(timer);

      if (!res.ok) {
        throw new Error(`MCP backend HTTP ${res.status}: ${res.statusText}`);
      }

      const json = await res.json();
      if (json.error) {
        throw new Error(json.error.message || `MCP Error ${json.error.code}`);
      }

      return json.result;
    } catch (err: any) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`Timeout connecting to backend/MCP server (${timeout}ms)`);
      }
      throw err;
    }
  }

  async callTool<T = any>(name: string, args: Record<string, any> = {}): Promise<T> {
    const rpcResult = await this.callRpc('tools/call', {
      name,
      arguments: args,
    });

    if (rpcResult?.isError) {
      const errMsg = rpcResult.content?.map((c: any) => c.text).filter(Boolean).join('\n') || 'Error in MCP tool call';
      throw new Error(errMsg);
    }

    if (Array.isArray(rpcResult?.content) && rpcResult.content.length > 0) {
      const first = rpcResult.content[0];
      if (first.type === 'text') {
        try {
          return JSON.parse(first.text);
        } catch {
          return first.text as unknown as T;
        }
      }
      if (first.data !== undefined) {
        return first.data;
      }
    }

    return rpcResult as T;
  }

  async querySql(sql: string, options?: { catalog?: string; dataset?: string; resource?: string }): Promise<{
    columns: string[];
    rows: any[][];
    row_count: number;
  }> {
    return this.callTool('datamesh_sql_query', {
      sql_query: sql,
      ...options,
    });
  }

  async readResource(resourceUriOrUrl: string): Promise<{
    uri: string;
    content: string;
    mime_type?: string;
  }> {
    return this.callTool('read_resource', {
      uri: resourceUriOrUrl,
    });
  }

  async listTools(): Promise<Array<{ name: string; description?: string; inputSchema?: any }>> {
    const res = await this.callRpc('tools/list', {});
    return res?.tools || [];
  }
}

export const datameshMcp = new DataMeshMcpClient();


