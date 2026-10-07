package domain

import (
	"fmt"
	"regexp"
	"strings"
	"time"
)

// LineageSource represents an upstream data source, raw URL, or parent dataset reference.
type LineageSource struct {
	Name        string `json:"name" yaml:"name"`
	Dataset     string `json:"dataset,omitempty" yaml:"dataset,omitempty"`
	Resource    string `json:"resource,omitempty" yaml:"resource,omitempty"`
	URL         string `json:"url,omitempty" yaml:"url,omitempty"`
	Format      string `json:"format,omitempty" yaml:"format,omitempty"`
	Hash        string `json:"hash,omitempty" yaml:"hash,omitempty"`
	Description string `json:"description,omitempty" yaml:"description,omitempty"`
}

// LineageTransformation represents an ETL activity, script, SQL query, or computational step.
type LineageTransformation struct {
	Tool        string                 `json:"tool" yaml:"tool"`
	Type        string                 `json:"type" yaml:"type"` // script, sql, cwl, dbt, duckdb, python
	Hash        string                 `json:"hash,omitempty" yaml:"hash,omitempty"`
	Description string                 `json:"description,omitempty" yaml:"description,omitempty"`
	Query       string                 `json:"query,omitempty" yaml:"query,omitempty"`
	Params      map[string]interface{} `json:"params,omitempty" yaml:"params,omitempty"`
}

// LineageInfo encapsulates OKF v0.2 / W3C PROV-O provenance metadata record.
type LineageInfo struct {
	DatasetID       string                  `json:"dataset_id" yaml:"dataset_id"`
	Title           string                  `json:"title,omitempty" yaml:"title,omitempty"`
	Version         string                  `json:"version,omitempty" yaml:"version,omitempty"`
	UpdatedAt       time.Time               `json:"updated_at,omitempty" yaml:"updated_at,omitempty"`
	Sources         []LineageSource         `json:"sources" yaml:"sources"`
	Transformations []LineageTransformation `json:"transformations" yaml:"transformations"`
	WasDerivedFrom  []string                `json:"was_derived_from" yaml:"was_derived_from"`
	Metadata        map[string]interface{}  `json:"metadata,omitempty" yaml:"metadata,omitempty"`
}

// LineageNode represents a dataset or external source vertex in the DAG.
type LineageNode struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	Type  string `json:"type"` // dataset, external_source
}

// LineageEdge represents a directed derivation arc (source -> target).
type LineageEdge struct {
	Source         string                 `json:"source"`
	Target         string                 `json:"target"`
	Label          string                 `json:"label,omitempty"`
	Transformation *LineageTransformation `json:"transformation,omitempty"`
}

// LineageGraph is the Directed Acyclic Graph (DAG) for dataset lineage and derivation analysis.
type LineageGraph struct {
	Nodes   map[string]LineageNode `json:"nodes"`
	Edges   []LineageEdge          `json:"edges"`
	Records map[string]LineageInfo `json:"records"`
}

// NewLineageGraph instantiates a blank LineageGraph.
func NewLineageGraph() *LineageGraph {
	return &LineageGraph{
		Nodes:   make(map[string]LineageNode),
		Edges:   make([]LineageEdge, 0),
		Records: make(map[string]LineageInfo),
	}
}

// Upstream returns all upstream ancestor datasets/sources that produced datasetID.
func (g *LineageGraph) Upstream(datasetID string) []string {
	visited := make([]string, 0)
	visitedMap := make(map[string]bool)
	queue := []string{datasetID}

	for len(queue) > 0 {
		nextQueue := make([]string, 0)
		for _, curr := range queue {
			for _, edge := range g.Edges {
				if edge.Target == curr && !visitedMap[edge.Source] && edge.Source != datasetID {
					visitedMap[edge.Source] = true
					visited = append(visited, edge.Source)
					nextQueue = append(nextQueue, edge.Source)
				}
			}
		}
		queue = nextQueue
	}
	return visited
}

// Downstream returns all downstream descendant datasets derived from datasetID.
func (g *LineageGraph) Downstream(datasetID string) []string {
	visited := make([]string, 0)
	visitedMap := make(map[string]bool)
	queue := []string{datasetID}

	for len(queue) > 0 {
		nextQueue := make([]string, 0)
		for _, curr := range queue {
			for _, edge := range g.Edges {
				if edge.Source == curr && !visitedMap[edge.Target] && edge.Target != datasetID {
					visitedMap[edge.Target] = true
					visited = append(visited, edge.Target)
					nextQueue = append(nextQueue, edge.Target)
				}
			}
		}
		queue = nextQueue
	}
	return visited
}

var cleanIDRegex = regexp.MustCompile(`[^a-zA-Z0-9_]`)

func cleanNodeID(raw string) string {
	return cleanIDRegex.ReplaceAllString(raw, "_")
}

// ToMermaid exports a Mermaid flowchart representation.
func (g *LineageGraph) ToMermaid(highlightID string) string {
	var sb strings.Builder
	sb.WriteString("flowchart LR\n")

	for nid, n := range g.Nodes {
		cid := cleanNodeID(nid)
		lbl := n.Title
		if lbl == "" {
			lbl = nid
		}
		lbl = strings.ReplaceAll(lbl, "\"", "'")
		if n.Type == "external_source" {
			sb.WriteString(fmt.Sprintf("    %s([\"%s\"])\n", cid, lbl))
		} else {
			sb.WriteString(fmt.Sprintf("    %s[\"%s\"]\n", cid, lbl))
		}
	}

	for _, edge := range g.Edges {
		sID := cleanNodeID(edge.Source)
		tID := cleanNodeID(edge.Target)
		if edge.Label != "" {
			lbl := strings.ReplaceAll(edge.Label, "\"", "'")
			sb.WriteString(fmt.Sprintf("    %s -->|\"%s\"| %s\n", sID, lbl, tID))
		} else {
			sb.WriteString(fmt.Sprintf("    %s --> %s\n", sID, tID))
		}
	}

	if highlightID != "" {
		hid := cleanNodeID(highlightID)
		if _, ok := g.Nodes[highlightID]; ok {
			sb.WriteString(fmt.Sprintf("    style %s fill:#ffefc2,stroke:#d97706,stroke-width:3px\n", hid))
		}
	}

	return strings.TrimRight(sb.String(), "\n")
}

// ToASCII exports a terminal ASCII hierarchy representation.
func (g *LineageGraph) ToASCII(rootID string) string {
	var sb strings.Builder
	targets := make([]string, 0)
	if rootID != "" {
		targets = append(targets, rootID)
	} else {
		for nid := range g.Nodes {
			targets = append(targets, nid)
		}
	}

	for _, tid := range targets {
		node := g.Nodes[tid]
		title := node.Title
		if title == "" {
			title = tid
		}
		up := g.Upstream(tid)
		down := g.Downstream(tid)

		sb.WriteString(fmt.Sprintf("Dataset: %s (%s)\n", tid, title))
		if len(up) > 0 {
			sb.WriteString("  ▲ Upstream (Fuentes/Insumos):\n")
			for _, u := range up {
				uNode := g.Nodes[u]
				uTitle := ""
				if uNode.Title != "" && uNode.Title != u {
					uTitle = fmt.Sprintf(" (%s)", uNode.Title)
				}
				lbl := ""
				for _, e := range g.Edges {
					if e.Source == u && e.Target == tid && e.Label != "" {
						lbl = fmt.Sprintf(" via [%s]", e.Label)
						break
					}
				}
				sb.WriteString(fmt.Sprintf("    - %s%s%s\n", u, uTitle, lbl))
			}
		} else {
			sb.WriteString("  ▲ Upstream: (Fuente primaria / raíz)\n")
		}

		if len(down) > 0 {
			sb.WriteString("  ▼ Downstream (Derivados / Resultados):\n")
			for _, d := range down {
				dNode := g.Nodes[d]
				dTitle := ""
				if dNode.Title != "" && dNode.Title != d {
					dTitle = fmt.Sprintf(" (%s)", dNode.Title)
				}
				lbl := ""
				for _, e := range g.Edges {
					if e.Source == tid && e.Target == d && e.Label != "" {
						lbl = fmt.Sprintf(" via [%s]", e.Label)
						break
					}
				}
				sb.WriteString(fmt.Sprintf("    - %s%s%s\n", d, dTitle, lbl))
			}
		}
		sb.WriteString("\n")
	}

	return strings.TrimSpace(sb.String())
}
