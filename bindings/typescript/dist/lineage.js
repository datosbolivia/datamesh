/**
 * DataMesh Sovereign Lineage System (OKF / ODKF v0.2 & W3C PROV-O).
 * Provides dataset provenance extraction, DAG graph building, multi-tier derivation
 * traversal up to RAW, Mermaid diagrams, and ASCII tree rendering.
 */
/**
 * Directed Acyclic Graph (DAG) for dataset lineage and derivation analysis.
 */
export class LineageGraph {
    nodes;
    edges;
    records;
    constructor(nodes = new Map(), edges = [], records = new Map()) {
        this.nodes = nodes;
        this.edges = edges;
        this.records = records;
    }
    /**
     * Returns ordered list of all upstream ancestor datasets/sources that produced dataset_id.
     */
    upstream(datasetId, maxDepth = 10) {
        const visited = [];
        let queue = [datasetId];
        let depth = 0;
        while (queue.length > 0 && depth < maxDepth) {
            const nextQueue = [];
            for (const curr of queue) {
                for (const edge of this.edges) {
                    if (edge.target === curr && !visited.includes(edge.source) && edge.source !== datasetId) {
                        visited.push(edge.source);
                        nextQueue.push(edge.source);
                    }
                }
            }
            queue = nextQueue;
            depth++;
        }
        return visited;
    }
    /**
     * Returns ordered list of all downstream descendant datasets derived from dataset_id.
     */
    downstream(datasetId, maxDepth = 10) {
        const visited = [];
        let queue = [datasetId];
        let depth = 0;
        while (queue.length > 0 && depth < maxDepth) {
            const nextQueue = [];
            for (const curr of queue) {
                for (const edge of this.edges) {
                    if (edge.source === curr && !visited.includes(edge.target) && edge.target !== datasetId) {
                        visited.push(edge.target);
                        nextQueue.push(edge.target);
                    }
                }
            }
            queue = nextQueue;
            depth++;
        }
        return visited;
    }
    /**
     * Traverses upstream derivations building a structured multi-level chain (Level 0 -> Level 1 -> Level 2 [RAW] -> Level 3 [Portal]).
     */
    getChain(datasetId, maxLevels = 3) {
        const chain = [];
        const rootNode = this.nodes.get(datasetId);
        const rootRec = this.records.get(datasetId);
        const rootTrans = rootRec?.transformations?.[0]?.description ||
            'Normalización dimensional y validación contra codelists SDMX';
        chain.push({
            level: 0,
            id: datasetId,
            title: rootNode?.title || rootRec?.title || datasetId,
            format: (rootNode?.format || 'csv').toLowerCase(),
            url: rootNode?.url || `data/subpedidos/${datasetId}.csv`,
            download_url: rootNode?.download_url || rootNode?.url || `data/subpedidos/${datasetId}.csv`,
            is_raw: false,
            transformation: rootTrans,
            description: rootNode?.description || rootRec?.metadata?.description || 'Componente analítico normalizado'
        });
        let currentId = datasetId;
        let currentLevel = 1;
        while (currentLevel <= maxLevels) {
            const parentEdge = this.edges.find(e => e.target === currentId);
            if (!parentEdge)
                break;
            const parentId = parentEdge.source;
            const parentNode = this.nodes.get(parentId);
            const parentRec = this.records.get(parentId);
            const isPortal = parentNode?.type === 'portal' || parentId.startsWith('http');
            const isRaw = Boolean(parentNode?.is_raw || (!isPortal && currentLevel >= 2) || (parentNode?.format && ['xlsx', 'xls'].includes(parentNode.format.toLowerCase())));
            const format = (parentNode?.format || (isPortal ? 'portal' : (isRaw ? 'xlsx' : 'parquet'))).toLowerCase();
            const transDesc = parentRec?.transformations?.[0]?.description ||
                parentEdge.transformation?.description ||
                parentEdge.label ||
                (isPortal ? 'Fuente Institucional Primaria' : (isRaw ? 'Publicación Oficial' : 'Ingesta CKAN (ETL Parquet)'));
            chain.push({
                level: currentLevel,
                id: parentId,
                title: parentNode?.title || parentRec?.title || parentId,
                format,
                url: parentNode?.url || (isPortal ? parentId : ''),
                download_url: parentNode?.download_url || parentNode?.url || '',
                is_raw: isRaw,
                transformation: transDesc,
                description: parentNode?.description || parentRec?.metadata?.description || (isPortal ? 'Publicación oficial en portal institucional' : (isRaw ? 'Insumo crudo original en planilla' : 'Dataset intermedio en CKAN'))
            });
            currentId = parentId;
            currentLevel++;
        }
        return chain;
    }
    /**
     * Renders Mermaid flowchart diagram representing dataset derivations.
     */
    toMermaid(highlightId) {
        const lines = ["flowchart LR"];
        const nodeIds = new Set();
        const cleanNodeId = (raw) => raw.replace(/[^a-zA-Z0-9_]/g, '_');
        for (const [nid, n] of this.nodes.entries()) {
            const cid = cleanNodeId(nid);
            nodeIds.add(cid);
            const lbl = (n.title || nid).replace(/"/g, "'");
            const shape = n.type === "dataset" ? `["${lbl}"]` : `(["${lbl}"])`;
            lines.push(`    ${cid}${shape}`);
        }
        for (const edge of this.edges) {
            const sId = cleanNodeId(edge.source);
            const tId = cleanNodeId(edge.target);
            if (edge.label) {
                const lbl = edge.label.replace(/"/g, "'");
                lines.push(`    ${sId} -->|${lbl}| ${tId}`);
            }
            else {
                lines.push(`    ${sId} --> ${tId}`);
            }
        }
        if (highlightId) {
            const hid = cleanNodeId(highlightId);
            if (nodeIds.has(hid)) {
                lines.push(`    style ${hid} fill:#ffefc2,stroke:#d97706,stroke-width:3px`);
            }
        }
        return lines.join("\n");
    }
    /**
     * Renders an ASCII tree showing derivations upstream or downstream with depth levels.
     */
    toAscii(rootId) {
        const out = [];
        const targets = rootId ? [rootId] : Array.from(this.nodes.keys());
        for (const tid of targets) {
            const node = this.nodes.get(tid);
            const title = node?.title || tid;
            const up = this.upstream(tid);
            out.push(`Dataset: ${tid} (${title})`);
            if (up.length > 0) {
                out.push("  ▲ Upstream (Procedencia hasta RAW):");
                const visited = new Set();
                const printUpstreamTree = (currId, indent, level) => {
                    if (visited.has(currId) || level > 10)
                        return;
                    visited.add(currId);
                    const parentEdges = this.edges.filter(e => e.target === currId);
                    for (const edge of parentEdges) {
                        const pId = edge.source;
                        const pNode = this.nodes.get(pId);
                        const pTitle = pNode?.title || pId;
                        const isRaw = pNode?.is_raw || level >= 2;
                        const rawTag = isRaw ? " [RAW]" : "";
                        const transLabel = edge.transformation?.description || edge.label || "";
                        const viaPart = transLabel ? ` via [${transLabel}]` : "";
                        out.push(`${indent}└─ Level ${level}${rawTag}: ${pId} (${pTitle})${viaPart}`);
                        printUpstreamTree(pId, indent + "    ", level + 1);
                    }
                };
                printUpstreamTree(tid, "    ", 1);
            }
        }
        return out.join("\n");
    }
    toDict() {
        const nodesObj = {};
        for (const [k, v] of this.nodes.entries()) {
            nodesObj[k] = v;
        }
        return {
            nodes: nodesObj,
            edges: this.edges,
        };
    }
}
/**
 * UseCase for dataset provenance, dependency extraction, and lineage graph analysis.
 */
export class DatasetLineageUseCase {
    extractFromDict(data, defaultId = '') {
        const did = String(data.name || data.id || data.dataset_id || defaultId || 'unnamed_dataset');
        const title = data.title || did;
        const lineageDict = (typeof data.lineage === 'object' && data.lineage !== null)
            ? data.lineage
            : (data.provenance || {});
        // Sources
        const rawSources = lineageDict.sources || data.sources || [];
        const sources = [];
        if (Array.isArray(rawSources)) {
            for (const s of rawSources) {
                if (typeof s === 'string') {
                    const clean = s.trim();
                    if (clean.startsWith('http://') || clean.startsWith('https://')) {
                        sources.push({ name: clean, url: clean });
                    }
                    else if (clean.includes(':')) {
                        const parts = clean.split(':');
                        sources.push({ name: clean, dataset: parts[0], resource: parts[1] });
                    }
                    else {
                        sources.push({ name: clean, dataset: clean });
                    }
                }
                else if (typeof s === 'object' && s !== null) {
                    sources.push({
                        name: String(s.name || s.title || s.dataset || s.url || 'unnamed_source'),
                        dataset: s.dataset,
                        resource: s.resource,
                        url: s.url || s.path,
                        format: s.format,
                        hash: s.hash || s.sha256,
                        description: s.description,
                    });
                }
            }
        }
        // Transformations
        const rawTransforms = lineageDict.transformations || data.transformations || [];
        const transforms = [];
        if (Array.isArray(rawTransforms)) {
            for (const t of rawTransforms) {
                if (typeof t === 'object' && t !== null) {
                    transforms.push({
                        tool: String(t.tool || t.name || 'transformation'),
                        type: t.type || 'script',
                        hash: t.hash || t.sha256,
                        description: t.description,
                        query: t.query || t.sql,
                        params: t.params || {},
                    });
                }
            }
        }
        // was_derived_from
        const derivedRaw = lineageDict.was_derived_from || lineageDict.derived_from || data.was_derived_from || [];
        const derived = [];
        if (Array.isArray(derivedRaw)) {
            derived.push(...derivedRaw.map(String));
        }
        else if (typeof derivedRaw === 'string') {
            derived.push(derivedRaw);
        }
        for (const s of sources) {
            const parent = s.name && s.name.includes(':')
                ? s.name
                : (s.dataset && s.resource ? `${s.dataset}:${s.resource}` : (s.dataset || s.name));
            if (parent && !derived.includes(parent) && parent !== did) {
                derived.push(parent);
            }
        }
        return {
            dataset_id: did,
            title,
            version: lineageDict.version || data.version,
            updated_at: lineageDict.updated_at || data.updated_at,
            sources,
            transformations: transforms,
            was_derived_from: derived,
            metadata: lineageDict.metadata || {},
        };
    }
    /**
     * Extracts primary and resource-level LineageInfo records from a manifest package.
     */
    extractRecordsFromPackage(manifest, defaultId = '') {
        const results = [];
        const primary = this.extractFromDict(manifest, defaultId);
        results.push(primary);
        const dsId = primary.dataset_id;
        const resources = Array.isArray(manifest.resources) ? manifest.resources : [];
        for (const r of resources) {
            if (typeof r === 'object' && r !== null) {
                const rName = r.name;
                if (rName && (r.lineage || r.was_derived_from || r.sources)) {
                    const rTriad = `${dsId}:${rName}`;
                    results.push(this.extractFromDict(r, rTriad));
                    results.push(this.extractFromDict(r, rName));
                }
            }
        }
        return results;
    }
    /**
     * Builds Lineage DAG graph from explicit lineage records or catalog maps.
     */
    buildGraph(records = []) {
        const collected = new Map();
        for (const r of records) {
            collected.set(r.dataset_id, r);
        }
        const nodes = new Map();
        const edges = [];
        // Add nodes
        for (const [dsId, rec] of collected.entries()) {
            const isPortal = dsId.startsWith('http');
            const isRaw = rec.metadata?.is_raw || dsId.includes('raw_') || ['xlsx', 'xls'].includes(String(rec.metadata?.format || '').toLowerCase());
            nodes.set(dsId, {
                id: dsId,
                title: rec.title || dsId,
                type: isPortal ? 'portal' : 'dataset',
                format: rec.metadata?.format,
                url: rec.metadata?.url || (isPortal ? dsId : undefined),
                download_url: rec.metadata?.download_url || rec.metadata?.url,
                is_raw: isRaw,
                description: rec.metadata?.description,
            });
        }
        // Build directed edges (parent -> child)
        for (const [dsId, rec] of collected.entries()) {
            const firstTrans = rec.transformations[0];
            const label = firstTrans?.description || firstTrans?.tool || undefined;
            for (const parentId of rec.was_derived_from) {
                if (!parentId || parentId === dsId)
                    continue;
                if (!nodes.has(parentId)) {
                    const isPortal = parentId.startsWith('http');
                    nodes.set(parentId, {
                        id: parentId,
                        title: parentId,
                        type: isPortal ? 'portal' : 'external_source',
                        url: isPortal ? parentId : undefined,
                        is_raw: isPortal || parentId.includes('raw_'),
                    });
                }
                edges.push({
                    source: parentId,
                    target: dsId,
                    label,
                    transformation: firstTrans,
                });
            }
        }
        return new LineageGraph(nodes, edges, collected);
    }
    /**
     * Calculates full lineage details for a given dataset showing upstream, downstream, and full level chain.
     */
    getLineage(datasetId, records = []) {
        const graph = this.buildGraph(records);
        let targetId = datasetId;
        if (!graph.nodes.has(targetId)) {
            const clean = targetId.toLowerCase().trim();
            for (const nid of graph.nodes.keys()) {
                if (nid.toLowerCase().trim() === clean) {
                    targetId = nid;
                    break;
                }
            }
        }
        const upstreamIds = graph.upstream(targetId);
        const downstreamIds = graph.downstream(targetId);
        const record = graph.records.get(targetId);
        const node = graph.nodes.get(targetId);
        const title = record?.title || node?.title || targetId;
        const chain = graph.getChain(targetId, 3);
        return {
            dataset_id: targetId,
            title,
            version: record?.version,
            updated_at: record?.updated_at,
            upstream: upstreamIds,
            downstream: downstreamIds,
            chain,
            sources: record?.sources || [],
            transformations: record?.transformations || [],
            mermaid: graph.toMermaid(targetId),
            ascii: graph.toAscii(targetId),
            graph: {
                nodes: Object.fromEntries(graph.nodes.entries()),
                edges: graph.edges,
            },
        };
    }
}
/**
 * Standard 1-line DataMesh lineage inspection function.
 */
export function getLineage(datasetId, options) {
    const usecase = new DatasetLineageUseCase();
    return usecase.getLineage(datasetId, options?.records);
}
