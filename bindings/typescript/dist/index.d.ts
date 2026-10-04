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
}
export interface DataPackage {
    name?: string;
    title?: string;
    description?: string;
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
export interface DataMeshClientOptions {
    catalogUrls?: string[];
    engine?: ExecutionEngine;
    proxyUrl?: string;
}
/**
 * Standard sovereign endpoints for OKF / ODKF v0.2 catalogs and portals.
 */
export declare const CANONICAL_ENDPOINTS: {
    readonly LLMS_TXT: "/llms.txt";
    readonly LLM_TXT: "/llm.txt";
    readonly LLMS_FULL_TXT: "/llms-full.txt";
    readonly RAW: "/raw";
};
/**
 * Matches table names in FROM and JOIN clauses (quoted or unquoted).
 */
export declare const TABLE_REF_PATTERN: RegExp;
/**
 * Matches quoted identifiers with colons (canonical triads).
 */
export declare const QUOTED_COLON_PATTERN: RegExp;
/**
 * Matches quoted identifiers with slashes (slash-separated triads or relative paths).
 */
export declare const QUOTED_SLASH_PATTERN: RegExp;
/**
 * Sanitizes text replacing non-alphanumeric chars with underscores.
 */
export declare function slugify(text: string): string;
/**
 * Known domains and suffixes with strict browser CORS restrictions.
 */
export declare const KNOWN_CORS_RESTRICTED_DOMAINS: string[];
/**
 * Standard CORS proxy templates.
 */
export declare const DEFAULT_PROXY_PROVIDERS: Record<string, (url: string) => string>;
/**
 * Checks if a given domain or URL is CORS restricted for client browsers.
 */
export declare function isCorsRestrictedDomain(url: string, restrictedDomains?: string[]): boolean;
/**
 * Pings a proxy or server endpoint to verify connectivity.
 */
export declare function pingProxy(urlOrTemplate: string, timeoutMs?: number): Promise<{
    ok: boolean;
    status?: number;
    error?: string;
}>;
/**
 * Normalizes remote URLs (e.g. GitHub blob/raw links to raw.githubusercontent.com for CORS compatibility).
 */
export declare function normalizeResourceUrl(url: string): string;
/**
 * Parses a DataPackage manifest from raw JSON or YAML content.
 * Accepts an optional custom YAML parser callback (e.g. js-yaml) or falls back to
 * JSON parsing and simple structural scanner.
 */
export declare function parseDataPackageManifest(rawContent: string, options?: {
    yamlParser?: (content: string) => any;
    filePath?: string;
}): DataPackage | null;
/**
 * Lightweight scanner extracting resource definitions from datapackage.yaml/yml text.
 */
export declare function parseSimpleYamlResources(text: string): Array<{
    name?: string;
    path?: string;
}>;
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
export declare function parseCanonicalUri(raw: string): ResourceTriad | null;
/**
 * Formats a ResourceTriad into canonical 'dataset:resource' or 'catalog:dataset:resource' string.
 */
export declare function toCanonicalTriad(triad: ResourceTriad): string;
/**
 * Formats a ResourceTriad into sovereign 'datamesh://...' URI.
 */
export declare function toCanonicalUri(triad: ResourceTriad): string;
/**
 * Returns the default catalog endpoint.
 * In a web browser, resolves to the current host's /llms.txt.
 * In headless/Node environments, defaults to the canonical Datos Bolivia catalog.
 */
export declare function getDefaultCatalogUrl(): string;
/**
 * Parses raw CSV/TSV text into column headers and rows, safely respecting quotes and multiline values.
 */
export declare function parseCsv(text: string, delimiter?: string): {
    columns: string[];
    rows: string[][];
};
/**
 * DuckDB WASM Client Engine for Browser execution.
 * Lazily loads DuckDB-WASM via dynamic import and executes full ANSI SQL.
 */
export declare class DuckDBBrowserEngine {
    private db;
    private conn;
    private initPromise;
    private registeredViews;
    init(): Promise<boolean>;
    executeSql(sqlQuery: string, fileRegistrations?: Record<string, string>): Promise<QueryResult | null>;
}
/**
 * DataMesh Sovereign Client SDK in TypeScript.
 * Provides client-side catalog federation, direct HTTP tabular streaming, and in-memory/DuckDB SQL querying.
 */
export declare class DataMeshClient {
    private catalogUrls;
    engine: ExecutionEngine;
    proxyUrl?: string;
    private duckdbEngine;
    private catalogCache;
    constructor(options?: DataMeshClientOptions | string[]);
    /**
     * Sets or updates the active CORS proxy URL or template.
     * e.g. "https://api.allorigins.win/raw?url={url}" or "https://corsproxy.io/?url={url}"
     */
    setProxy(proxyUrl?: string): void;
    /**
     * Formats a target URL through the configured proxy.
     */
    formatProxiedUrl(targetUrl: string, customProxy?: string): string;
    /**
     * Resolves any canonical triad ('ds:res', 'cat:ds:res'), sovereign URI ('datamesh://...'),
     * or direct URL into a physical fetchable URL.
     */
    resolveResource(uriOrTriad: string): Promise<string>;
    /**
     * Discovers sovereign data products across configured federated catalogs or a specified endpoint.
     * Leverages Go Core WASM runtime (window.DataMesh) when loaded, with pure JS fallback.
     */
    discover(url?: string): Promise<Catalog>;
    /**
     * Searches entries across sovereign catalogs matching title, description, or domain.
     * Leverages Go Core WASM runtime (window.DataMesh) when loaded, with pure JS fallback.
     */
    search(keyword: string, url?: string): Promise<CatalogEntry[]>;
    /**
     * Resolves an OKF v0.2 Data Product manifest, description, and resources from a node URI or URL.
     * Leverages Go Core WASM runtime (window.DataMesh) when loaded, with pure JS fallback.
     */
    get(uriOrUrl: string): Promise<DataProduct>;
    /**
     * Fetches and queries a tabular resource directly from the browser/client.
     * Supports canonical triad URIs (e.g. 'dataset:resource') or direct HTTP URLs.
     * Leverages Go Core WASM runtime (window.DataMesh) when loaded, with pure JS fallback.
     */
    query(req: QueryRequest): Promise<QueryResult>;
    /**
     * Runs in-memory filtering, keyword search, sorting, and pagination on parsed tabular data.
     */
    queryTable(table: {
        columns: string[];
        rows: string[][];
    }, req: Omit<QueryRequest, "resource_uri">): QueryResult;
    /**
     * Executes SQL against a remote resource, in-memory table, or canonical triad references.
     * If engine is 'duckdb', attempts execution via DuckDB-WASM with fallback to in-memory engine.
     */
    sql(sqlQuery: string, sourceOrOptions?: string | {
        columns: string[];
        rows: string[][];
    } | Record<string, string>, tableAlias?: string): Promise<QueryResult>;
    private executeWithDirectSource;
    private queryTableWithSql;
    private fetchSingleCatalog;
    private parseLLMSTxt;
    validate(target: string): Promise<ValidationReport>;
}
/**
 * Universal hook / factory function for initializing DataMesh client in web applications.
 */
export declare function useDataMesh(options?: DataMeshClientOptions): DataMeshClient;
export declare const datamesh: DataMeshClient;
export declare const discover: (url?: string) => Promise<Catalog>;
export declare const search: (keyword: string, url?: string) => Promise<CatalogEntry[]>;
export declare const get: (uriOrUrl: string) => Promise<DataProduct>;
export declare const query: (req: QueryRequest) => Promise<QueryResult>;
export declare const sql: (sqlQuery: string, sourceOrOptions?: string | {
    columns: string[];
    rows: string[][];
} | Record<string, string>, tableAlias?: string) => Promise<QueryResult>;
export declare const validate: (target: string) => Promise<ValidationReport>;
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
export declare class DataMeshMcpClient {
    private serverUrl;
    private timeoutMs;
    private headers;
    private requestId;
    constructor(config?: Partial<McpServerConfig>);
    setServerUrl(url: string): void;
    ping(): Promise<boolean>;
    callRpc(method: string, params?: Record<string, any>, customTimeout?: number): Promise<any>;
    callTool<T = any>(name: string, args?: Record<string, any>): Promise<T>;
    querySql(sql: string, options?: {
        catalog?: string;
        dataset?: string;
        resource?: string;
    }): Promise<{
        columns: string[];
        rows: any[][];
        row_count: number;
    }>;
    readResource(resourceUriOrUrl: string): Promise<{
        uri: string;
        content: string;
        mime_type?: string;
    }>;
    listTools(): Promise<Array<{
        name: string;
        description?: string;
        inputSchema?: any;
    }>>;
}
export declare const datameshMcp: DataMeshMcpClient;
