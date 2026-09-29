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
  resource_uri: string;
  filters?: Record<string, string>;
  limit?: number;
}

export interface QueryResult {
  columns: string[];
  rows: string[][];
  row_count: number;
}

/**
 * DataMesh WASM and Browser Client
 */
export class DataMeshClient {
  private catalogUrls: string[];

  constructor(catalogUrls: string[] = ["https://datosbolivia.github.io/llms.txt"]) {
    this.catalogUrls = catalogUrls;
  }

  /**
   * Discovers catalogs across all configured sovereign endpoints or a specific URL.
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
        } catch (e) {
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
   * Searches entries across sovereign catalogs.
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
   * Queries in-memory tabular CSV resource in browser.
   */
  async query(req: QueryRequest): Promise<QueryResult> {
    const res = await fetch(req.resource_uri);
    if (!res.ok) {
      throw new Error(`Failed to fetch tabular resource: HTTP ${res.status}`);
    }
    const text = await res.text();
    return this.executeCsvQuery(text, req.filters, req.limit);
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

  private executeCsvQuery(
    csvContent: string,
    filters?: Record<string, string>,
    limit?: number
  ): QueryResult {
    const lines = csvContent.split("\n").filter((l) => l.trim() !== "");
    if (lines.length === 0) {
      return { columns: [], rows: [], row_count: 0 };
    }

    const columns = lines[0].split(",").map((c) => c.trim());
    const colMap: Record<string, number> = {};
    columns.forEach((col, idx) => {
      colMap[col.toLowerCase()] = idx;
    });

    const filterIndices: Record<number, string> = {};
    if (filters) {
      for (const [k, v] of Object.entries(filters)) {
        const lowerK = k.toLowerCase().trim();
        if (colMap[lowerK] !== undefined) {
          filterIndices[colMap[lowerK]] = v.toLowerCase().trim();
        }
      }
    }

    const matchedRows: string[][] = [];

    for (let i = 1; i < lines.length; i++) {
      const row = lines[i].split(",").map((c) => c.trim());
      let matches = true;

      for (const [idxStr, expVal] of Object.entries(filterIndices)) {
        const idx = Number(idxStr);
        if (!row[idx] || row[idx].toLowerCase() !== expVal) {
          matches = false;
          break;
        }
      }

      if (matches) {
        matchedRows.push(row);
        if (limit && matchedRows.length >= limit) {
          break;
        }
      }
    }

    return {
      columns,
      rows: matchedRows,
      row_count: matchedRows.length,
    };
  }
}

export const datamesh = new DataMeshClient();
