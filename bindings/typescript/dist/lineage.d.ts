/**
 * DataMesh Sovereign Lineage System (OKF / ODKF v0.2 & W3C PROV-O).
 * Provides dataset provenance extraction, DAG graph building, multi-tier derivation
 * traversal up to RAW, Mermaid diagrams, and ASCII tree rendering.
 */
export interface LineageSource {
    name: string;
    dataset?: string;
    resource?: string;
    url?: string;
    format?: string;
    hash?: string;
    description?: string;
}
export interface LineageTransformation {
    tool: string;
    type?: string;
    hash?: string;
    description?: string;
    query?: string;
    params?: Record<string, any>;
}
export interface EpistemicActor {
    by: string;
    at?: string;
    role?: string;
    verdict?: "verified" | "refuted" | "pending" | string;
    trust_tier?: "unverified" | "machine-confirmed" | "human-reviewed" | string;
    signature?: Record<string, any>;
    metadata?: Record<string, any>;
}
export interface LineageInfo {
    dataset_id: string;
    title?: string;
    version?: string;
    updated_at?: string;
    emitter?: EpistemicActor;
    attester?: EpistemicActor;
    ref?: string;
    status?: string;
    supersedes?: string;
    nature?: string;
    sources: LineageSource[];
    transformations: LineageTransformation[];
    was_derived_from: string[];
    metadata?: Record<string, any>;
}
export interface LineageNode {
    id: string;
    title: string;
    type: "dataset" | "resource" | "external_source" | "portal";
    format?: string;
    url?: string;
    download_url?: string;
    is_raw?: boolean;
    description?: string;
}
export interface LineageEdge {
    source: string;
    target: string;
    label?: string;
    transformation?: LineageTransformation;
}
export interface LineageLevelItem {
    level: number;
    id: string;
    title: string;
    format: string;
    url?: string;
    download_url?: string;
    is_raw: boolean;
    transformation?: string;
    description?: string;
}
export interface LineageResult {
    dataset_id: string;
    title: string;
    version?: string;
    updated_at?: string;
    upstream: string[];
    downstream: string[];
    chain: LineageLevelItem[];
    sources: LineageSource[];
    transformations: LineageTransformation[];
    mermaid: string;
    ascii: string;
    graph: {
        nodes: Record<string, LineageNode>;
        edges: LineageEdge[];
    };
}
/**
 * Directed Acyclic Graph (DAG) for dataset lineage and derivation analysis.
 */
export declare class LineageGraph {
    nodes: Map<string, LineageNode>;
    edges: LineageEdge[];
    records: Map<string, LineageInfo>;
    constructor(nodes?: Map<string, LineageNode>, edges?: LineageEdge[], records?: Map<string, LineageInfo>);
    /**
     * Returns ordered list of all upstream ancestor datasets/sources that produced dataset_id.
     */
    upstream(datasetId: string, maxDepth?: number): string[];
    /**
     * Returns ordered list of all downstream descendant datasets derived from dataset_id.
     */
    downstream(datasetId: string, maxDepth?: number): string[];
    /**
     * Traverses upstream derivations building a structured multi-level chain (Level 0 -> Level 1 -> Level 2 [RAW] -> Level 3 [Portal]).
     */
    getChain(datasetId: string, maxLevels?: number): LineageLevelItem[];
    /**
     * Renders Mermaid flowchart diagram representing dataset derivations.
     */
    toMermaid(highlightId?: string): string;
    /**
     * Renders an ASCII tree showing derivations upstream or downstream with depth levels.
     */
    toAscii(rootId?: string): string;
    toDict(): Record<string, any>;
}
/**
 * UseCase for dataset provenance, dependency extraction, and lineage graph analysis.
 */
export declare class DatasetLineageUseCase {
    extractFromDict(data: Record<string, any>, defaultId?: string): LineageInfo;
    /**
     * Extracts primary and resource-level LineageInfo records from a manifest package.
     */
    extractRecordsFromPackage(manifest: Record<string, any>, defaultId?: string): LineageInfo[];
    /**
     * Builds Lineage DAG graph from explicit lineage records or catalog maps.
     */
    buildGraph(records?: LineageInfo[]): LineageGraph;
    /**
     * Calculates full lineage details for a given dataset showing upstream, downstream, and full level chain.
     */
    getLineage(datasetId: string, records?: LineageInfo[]): LineageResult;
}
/**
 * Standard 1-line DataMesh lineage inspection function.
 */
export declare function getLineage(datasetId: string, options?: {
    records?: LineageInfo[];
}): LineageResult;
