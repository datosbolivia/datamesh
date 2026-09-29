/**
 * Standard sovereign endpoints for OKF / ODKF v0.2 catalogs and portals.
 */
export const CANONICAL_ENDPOINTS = {
    LLMS_TXT: "/llms.txt",
    LLM_TXT: "/llm.txt",
    LLMS_FULL_TXT: "/llms-full.txt",
    RAW: "/raw",
};
/**
 * Matches table names in FROM and JOIN clauses (quoted or unquoted).
 */
export const TABLE_REF_PATTERN = /\b(?:FROM|JOIN)\s+(?:ONLY\s+)?(?:["']([^"']+)["']|([a-zA-Z0-9_\-\.:/]+))/gi;
/**
 * Matches quoted identifiers with colons (canonical triads).
 */
export const QUOTED_COLON_PATTERN = /["']([^"':\s]+:[^"']+)["']/g;
/**
 * Sanitizes text replacing non-alphanumeric chars with underscores.
 */
export function slugify(text) {
    return text.toLowerCase().replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}
/**
 * Normalizes remote URLs (e.g. GitHub blob/raw links to raw.githubusercontent.com for CORS compatibility).
 */
export function normalizeResourceUrl(url) {
    if (!url)
        return url;
    const trimmed = url.trim().replace(/^['"`]|['"`]$/g, '');
    const githubBlobMatch = trimmed.match(/^https?:\/\/(?:www\.)?github\.com\/([^/]+)\/([^/]+)\/(?:blob|raw)\/([^/]+)\/(.+)$/);
    if (githubBlobMatch) {
        const [, user, repo, branch, path] = githubBlobMatch;
        return `https://raw.githubusercontent.com/${user}/${repo}/${branch}/${path}`;
    }
    return trimmed;
}
/**
 * Lightweight scanner extracting resource definitions from datapackage.yaml/yml text.
 */
export function parseSimpleYamlResources(text) {
    const resources = [];
    const lines = text.split('\n');
    let inResources = false;
    let currentRes = null;
    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line || line.startsWith('#'))
            continue;
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
                    if (key === 'name')
                        currentRes.name = val;
                    else if (key === 'path')
                        currentRes.path = val;
                }
            }
            else if (currentRes) {
                const colonIdx = line.indexOf(':');
                if (colonIdx > 0) {
                    const key = line.substring(0, colonIdx).trim();
                    const val = line.substring(colonIdx + 1).trim().replace(/^['"]|['"]$/g, '');
                    if (key === 'name')
                        currentRes.name = val;
                    else if (key === 'path')
                        currentRes.path = val;
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
 * Parses any canonical triad, datamesh:// URI, or table identifier into a structured ResourceTriad.
 * Supports:
 * - 'catalogo:dataset:resource' (3 parts)
 * - 'dataset:resource' (2 parts)
 * - 'datamesh://catalogo/dataset/resource'
 * - 'datamesh://dataset/resource'
 */
export function parseCanonicalUri(raw) {
    const trimmed = raw.trim().replace(/^['"`]|['"`]$/g, '');
    if (!trimmed)
        return null;
    // 1. datamesh:// or odkf:// scheme
    if (trimmed.startsWith("datamesh://") || trimmed.startsWith("odkf://")) {
        const clean = trimmed.split("://")[1];
        const parts = clean.split("/").map((p) => p.trim()).filter(Boolean);
        if (parts.length >= 3) {
            return { catalog: parts[0], dataset: parts[1], resource: parts[2] };
        }
        else if (parts.length === 2) {
            return { dataset: parts[0], resource: parts[1] };
        }
        return null;
    }
    // 2. Colon-separated format ('cat:ds:res' or 'ds:res')
    if (trimmed.includes(":") && !trimmed.startsWith("http://") && !trimmed.startsWith("https://") && !trimmed.startsWith("file://")) {
        const parts = trimmed.split(":");
        if (parts.length === 3) {
            const cat = parts[0].trim();
            const ds = parts[1].trim();
            const res = parts[2].trim();
            if (ds && res) {
                return { catalog: cat || undefined, dataset: ds, resource: res };
            }
        }
        else if (parts.length === 2) {
            const ds = parts[0].trim();
            const res = parts[1].trim();
            if (ds && res) {
                return { dataset: ds, resource: res };
            }
        }
    }
    return null;
}
/**
 * Formats a ResourceTriad into canonical 'dataset:resource' or 'catalog:dataset:resource' string.
 */
export function toCanonicalTriad(triad) {
    if (triad.catalog) {
        return `${triad.catalog}:${triad.dataset}:${triad.resource}`;
    }
    return `${triad.dataset}:${triad.resource}`;
}
/**
 * Formats a ResourceTriad into sovereign 'datamesh://...' URI.
 */
export function toCanonicalUri(triad) {
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
export function getDefaultCatalogUrl() {
    if (typeof window !== "undefined" && window.location?.origin) {
        return `${window.location.origin}/llms.txt`;
    }
    return "https://datosbolivia.github.io/llms.txt";
}
/**
 * Parses raw CSV/TSV text into column headers and rows, safely respecting quotes and multiline values.
 */
export function parseCsv(text, delimiter) {
    const clean = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    if (!clean.trim()) {
        return { columns: [], rows: [] };
    }
    const delim = delimiter || (clean.split("\n")[0].includes("\t") ? "\t" : ",");
    const rows = [];
    let currentRow = [];
    let currentField = "";
    let inQuotes = false;
    for (let i = 0; i < clean.length; i++) {
        const char = clean[i];
        const nextChar = clean[i + 1];
        if (char === '"') {
            if (inQuotes && nextChar === '"') {
                currentField += '"';
                i++;
            }
            else {
                inQuotes = !inQuotes;
            }
        }
        else if (char === delim && !inQuotes) {
            currentRow.push(currentField.trim());
            currentField = "";
        }
        else if (char === "\n" && !inQuotes) {
            currentRow.push(currentField.trim());
            if (currentRow.some((f) => f.length > 0)) {
                rows.push(currentRow);
            }
            currentRow = [];
            currentField = "";
        }
        else {
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
    db = null;
    conn = null;
    initPromise = null;
    registeredViews = new Set();
    async init() {
        if (this.conn)
            return true;
        if (this.initPromise)
            return this.initPromise;
        this.initPromise = (async () => {
            if (typeof window === "undefined") {
                return false;
            }
            try {
                const duckdbUrl = "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.28.0/+esm";
                const duckdb = await (Function("url", "return import(url)")(duckdbUrl));
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
            }
            catch (err) {
                console.warn("[DataMeshClient] DuckDB-WASM unavailable, falling back to in-memory engine:", err);
                this.db = null;
                this.conn = null;
                return false;
            }
        })();
        return this.initPromise;
    }
    async executeSql(sqlQuery, fileRegistrations) {
        const ready = await this.init();
        if (!ready || !this.conn)
            return null;
        try {
            if (fileRegistrations && this.db) {
                for (const [name, contentOrUrl] of Object.entries(fileRegistrations)) {
                    try {
                        if (contentOrUrl.startsWith("http://") || contentOrUrl.startsWith("https://") || contentOrUrl.startsWith("/")) {
                            await this.db.registerFileURL(name, contentOrUrl, 4, false);
                        }
                        else {
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
                            }
                            catch {
                                // view creation fallback
                            }
                        }
                    }
                    catch {
                        // view registration retry
                    }
                }
            }
            const arrowTable = await this.conn.query(sqlQuery);
            const columns = arrowTable.schema.fields.map((f) => f.name);
            const rows = [];
            for (let i = 0; i < arrowTable.numRows; i++) {
                const row = [];
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
        }
        catch (err) {
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
    catalogUrls;
    engine;
    duckdbEngine;
    catalogCache = null;
    constructor(options = {}) {
        if (Array.isArray(options)) {
            this.catalogUrls = options.length > 0 ? options : [getDefaultCatalogUrl()];
            this.engine = "duckdb";
        }
        else {
            this.catalogUrls = options.catalogUrls && options.catalogUrls.length > 0
                ? options.catalogUrls
                : [getDefaultCatalogUrl()];
            this.engine = options.engine || "duckdb";
        }
        this.duckdbEngine = new DuckDBBrowserEngine();
    }
    /**
     * Resolves any canonical triad ('ds:res', 'cat:ds:res'), sovereign URI ('datamesh://...'),
     * or direct URL into a physical fetchable URL.
     */
    async resolveResource(uriOrTriad) {
        const trimmed = uriOrTriad.trim().replace(/^['"`]|['"`]$/g, '');
        if (trimmed.startsWith("http://") ||
            trimmed.startsWith("https://") ||
            trimmed.startsWith("file://") ||
            trimmed.startsWith("/")) {
            return normalizeResourceUrl(trimmed);
        }
        const parsed = parseCanonicalUri(trimmed);
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
                        let resList = [];
                        if (dpUrl.endsWith('.json')) {
                            const pkg = await resp.json();
                            if (pkg.resources && Array.isArray(pkg.resources)) {
                                resList = pkg.resources;
                            }
                        }
                        else {
                            const text = await resp.text();
                            resList = parseSimpleYamlResources(text);
                        }
                        if (resList.length > 0) {
                            const foundRes = resList.find((r) => {
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
                }
                catch {
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
     */
    async discover(url) {
        const targets = url ? [url] : this.catalogUrls;
        if (!url && this.catalogCache && targets.length === this.catalogUrls.length) {
            return this.catalogCache;
        }
        if (targets.length === 1) {
            const single = await this.fetchSingleCatalog(targets[0]);
            if (!url)
                this.catalogCache = single;
            return single;
        }
        const combinedEntries = [];
        const sourceCatalogs = [];
        const seen = new Set();
        await Promise.all(targets.map(async (target) => {
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
            }
            catch {
                // resilient discovery: keep remaining catalogs
            }
        }));
        const result = {
            title: "DataMesh Federated Catalog",
            description: "Aggregated decentralized sovereign data products",
            source_catalogs: sourceCatalogs,
            entries: combinedEntries,
        };
        if (!url)
            this.catalogCache = result;
        return result;
    }
    /**
     * Searches entries across sovereign catalogs matching title, description, or domain.
     */
    async search(keyword, url) {
        const cat = await this.discover(url);
        const kw = keyword.toLowerCase();
        return cat.entries.filter((e) => e.title.toLowerCase().includes(kw) ||
            e.description.toLowerCase().includes(kw) ||
            e.domain.toLowerCase().includes(kw));
    }
    /**
     * Fetches and queries a tabular resource directly from the browser/client.
     * Supports canonical triad URIs (e.g. 'dataset:resource') or direct HTTP URLs.
     */
    async query(req) {
        if (!req.resource_uri) {
            throw new Error("QueryRequest requires a 'resource_uri'");
        }
        // Resolves canonical URI ('air_quality:mediciones', 'datamesh://...', or direct URL)
        const resolvedUrl = await this.resolveResource(req.resource_uri);
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
    queryTable(table, req) {
        const { columns, rows } = table;
        const colMap = {};
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
            filtered = filtered.filter((row) => row.some((cell) => (cell || "").toLowerCase().includes(q)));
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
    async sql(sqlQuery, sourceOrOptions, tableAlias = "resource") {
        // 1. Direct table object passed
        if (sourceOrOptions && typeof sourceOrOptions === "object" && "columns" in sourceOrOptions) {
            return this.executeWithDirectSource(sqlQuery, sourceOrOptions, tableAlias);
        }
        // 2. Direct single URL string passed with table alias
        if (typeof sourceOrOptions === "string" &&
            (sourceOrOptions.startsWith("http://") || sourceOrOptions.startsWith("https://") || sourceOrOptions.startsWith("/"))) {
            return this.executeWithDirectSource(sqlQuery, sourceOrOptions, tableAlias);
        }
        const tableMapping = sourceOrOptions && typeof sourceOrOptions === "object" && !("columns" in sourceOrOptions)
            ? sourceOrOptions
            : {};
        // 3. Extract table references from SQL query
        const tableRefs = [];
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
        // 4. Resolve physical URLs for each table reference
        const resolvedTableUrls = {};
        for (const ref of tableRefs) {
            if (tableMapping[ref]) {
                resolvedTableUrls[ref] = tableMapping[ref];
            }
            else {
                const resolved = await this.resolveResource(ref);
                resolvedTableUrls[ref] = resolved;
            }
        }
        // 5. DuckDB Execution
        if (this.engine === "duckdb") {
            const fileRegistrations = {};
            for (const [ref, url] of Object.entries(resolvedTableUrls)) {
                fileRegistrations[ref] = url;
                const clean = slugify(ref);
                if (clean)
                    fileRegistrations[clean] = url;
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
    async executeWithDirectSource(sqlQuery, source, tableAlias) {
        if (this.engine === "duckdb") {
            let dataContent;
            if (typeof source === "string") {
                dataContent = normalizeResourceUrl(source);
            }
            else {
                let csvStr = source.columns.map((c) => `"${c.replace(/"/g, '""')}"`).join(",") + "\n";
                source.rows.forEach((r) => {
                    csvStr += r.map((c) => `"${(c || "").replace(/"/g, '""')}"`).join(",") + "\n";
                });
                dataContent = csvStr;
            }
            const fileRegistrations = {
                [tableAlias]: dataContent,
                resource: dataContent,
            };
            const sAlias = slugify(tableAlias);
            if (sAlias)
                fileRegistrations[sAlias] = dataContent;
            const fromMatches = Array.from(sqlQuery.matchAll(TABLE_REF_PATTERN));
            for (const m of fromMatches) {
                const ref = (m[1] || m[2] || "").trim();
                if (ref) {
                    fileRegistrations[ref] = dataContent;
                    const s = slugify(ref);
                    if (s)
                        fileRegistrations[s] = dataContent;
                }
            }
            const quotedMatches = Array.from(sqlQuery.matchAll(QUOTED_COLON_PATTERN));
            for (const m of quotedMatches) {
                const ref = (m[1] || "").trim();
                if (ref) {
                    fileRegistrations[ref] = dataContent;
                    const s = slugify(ref);
                    if (s)
                        fileRegistrations[s] = dataContent;
                }
            }
            const duckResult = await this.duckdbEngine.executeSql(sqlQuery, fileRegistrations);
            if (duckResult) {
                return duckResult;
            }
        }
        let table;
        if (typeof source === "string") {
            const res = await fetch(source);
            if (!res.ok) {
                throw new Error(`Failed to fetch tabular resource: HTTP ${res.status}`);
            }
            const text = await res.text();
            table = parseCsv(text);
        }
        else {
            table = source;
        }
        return this.queryTableWithSql(table, sqlQuery);
    }
    queryTableWithSql(table, sqlQuery) {
        const normalizedSql = sqlQuery.trim();
        // Extract LIMIT and OFFSET
        let limit;
        let offset;
        const limitMatch = normalizedSql.match(/\bLIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?/i);
        if (limitMatch) {
            limit = parseInt(limitMatch[1], 10);
            if (limitMatch[2]) {
                offset = parseInt(limitMatch[2], 10);
            }
        }
        // Extract ORDER BY
        let sortBy;
        let sortDir = "asc";
        const orderMatch = normalizedSql.match(/\bORDER\s+BY\s+([a-zA-Z0-9_]+)(?:\s+(ASC|DESC))?/i);
        if (orderMatch) {
            sortBy = orderMatch[1];
            if (orderMatch[2] && orderMatch[2].toUpperCase() === "DESC") {
                sortDir = "desc";
            }
        }
        // Extract WHERE filters
        const filters = {};
        let search;
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
            const colIndices = [];
            const outCols = [];
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
    async fetchSingleCatalog(target) {
        const res = await fetch(target);
        if (!res.ok) {
            throw new Error(`Failed to fetch catalog: HTTP ${res.status}`);
        }
        const text = await res.text();
        return this.parseLLMSTxt(text, target);
    }
    parseLLMSTxt(content, sourceUrl) {
        const lines = content.split("\n");
        let title = "";
        let description = "";
        const entries = [];
        const entryRegex = /^-\s*\[(.*?)\]\((.*?)\)(?::\s*(.*))?$/;
        const domainRegex = /\(Dominio:\s*([^)]*?)(?:\.|\)|Recursos:)/;
        for (const rawLine of lines) {
            const line = rawLine.trim();
            if (!line)
                continue;
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
                }
                catch {
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
}
/**
 * Universal hook / factory function for initializing DataMesh client in web applications.
 */
export function useDataMesh(options) {
    return new DataMeshClient(options);
}
export const datamesh = new DataMeshClient();
