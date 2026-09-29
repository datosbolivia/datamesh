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

export interface QueryRequest {
  resource_uri?: string;
  filters?: Record<string, string>;
  search?: string;
  sort_by?: string;
  sort_direction?: "asc" | "desc";
  limit?: number;
  offset?: number;
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
  private duckdbEngine: DuckDBBrowserEngine;

  constructor(options: DataMeshClientOptions | string[] = {}) {
    if (Array.isArray(options)) {
      this.catalogUrls = options.length > 0 ? options : [getDefaultCatalogUrl()];
      this.engine = "duckdb";
    } else {
      this.catalogUrls = options.catalogUrls && options.catalogUrls.length > 0
        ? options.catalogUrls
        : [getDefaultCatalogUrl()];
      this.engine = options.engine || "duckdb";
    }
    this.duckdbEngine = new DuckDBBrowserEngine();
  }

  /**
   * Discovers sovereign data products across configured federated catalogs or a specified endpoint.
   */
  async discover(url?: string): Promise<Catalog> {
    const targets = url ? [url] : this.catalogUrls;

    if (targets.length === 1) {
      return this.fetchSingleCatalog(targets[0]);
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

    return {
      title: "DataMesh Federated Catalog",
      description: "Aggregated decentralized sovereign data products",
      source_catalogs: sourceCatalogs,
      entries: combinedEntries,
    };
  }

  /**
   * Searches entries across sovereign catalogs matching title, description, or domain.
   */
  async search(keyword: string, url?: string): Promise<CatalogEntry[]> {
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
   * Fetches and queries a tabular resource directly from the browser/client.
   */
  async query(req: QueryRequest): Promise<QueryResult> {
    if (!req.resource_uri) {
      throw new Error("QueryRequest requires a 'resource_uri'");
    }

    const res = await fetch(req.resource_uri);
    if (!res.ok) {
      throw new Error(`Failed to fetch tabular resource: HTTP ${res.status}`);
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
   * Executes SQL against a remote resource or in-memory table.
   * If engine is 'duckdb', attempts execution via DuckDB-WASM with fallback to in-memory engine.
   */
  async sql(
    sqlQuery: string,
    source: string | { columns: string[]; rows: string[][] },
    tableAlias: string = "resource"
  ): Promise<QueryResult> {
    // 1. Attempt DuckDB execution if configured
    if (this.engine === "duckdb") {
      let fileRegistrations: Record<string, string> | undefined;
      if (typeof source === "string") {
        fileRegistrations = { [tableAlias]: source };
      } else {
        let csvStr = source.columns.map((c) => `"${c.replace(/"/g, '""')}"`).join(",") + "\n";
        source.rows.forEach((r) => {
          csvStr += r.map((c) => `"${(c || "").replace(/"/g, '""')}"`).join(",") + "\n";
        });
        fileRegistrations = { [tableAlias]: csvStr };
      }

      const duckResult = await this.duckdbEngine.executeSql(sqlQuery, fileRegistrations);
      if (duckResult) {
        return duckResult;
      }
    }

    // 2. In-memory SQL execution fallback
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
}

export const datamesh = new DataMeshClient();
