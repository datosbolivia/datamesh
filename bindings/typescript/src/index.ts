export interface CatalogEntry {
  title: string;
  uri: string;
  resolved_url: string;
  description: string;
  domain: string;
  resources?: string[];
}

export interface Catalog {
  title: string;
  description: string;
  source_url: string;
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

/**
 * DataMesh WASM and Browser Client
 */
export class DataMeshClient {
  private catalogUrl: string;

  constructor(catalogUrl: string = "https://datosbolivia.github.io/llms.txt") {
    this.catalogUrl = catalogUrl;
  }

  /**
   * Discovers the catalog using browser fetch and parses llms.txt format in-memory.
   */
  async discover(url?: string): Promise<Catalog> {
    const target = url || this.catalogUrl;
    const res = await fetch(target);
    if (!res.ok) {
      throw new Error(`Failed to fetch catalog: HTTP ${res.status}`);
    }
    const text = await res.text();
    return this.parseLLMSTxt(text, target);
  }

  /**
   * Searches entries in the sovereign catalog.
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

        const resolvedUrl = new URL(rawUri, sourceUrl).toString();

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
