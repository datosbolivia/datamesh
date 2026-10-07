package usecases

import (
	"context"
	"encoding/json"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"gopkg.in/yaml.v3"
)

// LineageUseCase orchestrates provenance analysis, dataset derivation, and DAG traversal.
type LineageUseCase struct {
	defaultSearchDirs []string
}

// NewLineageUseCase creates a new LineageUseCase.
func NewLineageUseCase(defaultSearchDirs ...string) *LineageUseCase {
	return &LineageUseCase{
		defaultSearchDirs: defaultSearchDirs,
	}
}

// ExtractFromFile extracts LineageInfo from a yaml, json or markdown file.
func (uc *LineageUseCase) ExtractFromFile(filePath string) (*domain.LineageInfo, error) {
	content, err := os.ReadFile(filePath)
	if err != nil {
		return nil, err
	}

	fname := strings.ToLower(filepath.Base(filePath))
	parentName := filepath.Base(filepath.Dir(filePath))

	if strings.HasSuffix(fname, ".yaml") || strings.HasSuffix(fname, ".yml") {
		var raw map[string]interface{}
		if err := yaml.Unmarshal(content, &raw); err != nil {
			return nil, err
		}
		return uc.extractFromMap(raw, parentName), nil
	} else if strings.HasSuffix(fname, ".json") {
		var raw map[string]interface{}
		if err := json.Unmarshal(content, &raw); err != nil {
			return nil, err
		}
		return uc.extractFromMap(raw, parentName), nil
	} else if strings.HasSuffix(fname, ".md") {
		return uc.extractFromMarkdown(string(content), parentName), nil
	}

	return nil, nil
}

func (uc *LineageUseCase) extractFromMarkdown(markdownText string, defaultID string) *domain.LineageInfo {
	lines := strings.Split(markdownText, "\n")
	if len(lines) == 0 || strings.TrimSpace(lines[0]) != "---" {
		return nil
	}

	endIdx := -1
	for i := 1; i < len(lines); i++ {
		if strings.TrimSpace(lines[i]) == "---" {
			endIdx = i
			break
		}
	}
	if endIdx == -1 {
		return nil
	}

	frontmatterText := strings.Join(lines[1:endIdx], "\n")
	var raw map[string]interface{}
	if err := yaml.Unmarshal([]byte(frontmatterText), &raw); err != nil {
		return nil
	}

	return uc.extractFromMap(raw, defaultID)
}

func (uc *LineageUseCase) extractFromMap(raw map[string]interface{}, defaultID string) *domain.LineageInfo {
	id := defaultID
	if n, ok := raw["name"].(string); ok && n != "" {
		id = n
	} else if i, ok := raw["id"].(string); ok && i != "" {
		id = i
	}

	title := id
	if t, ok := raw["title"].(string); ok && t != "" {
		title = t
	}

	version := ""
	if v, ok := raw["version"].(string); ok {
		version = v
	}

	sources := make([]domain.LineageSource, 0)
	transformations := make([]domain.LineageTransformation, 0)
	derivedFrom := make([]string, 0)

	// Check lineage block or root
	var lineageMap map[string]interface{}
	if lm, ok := raw["lineage"].(map[string]interface{}); ok {
		lineageMap = lm
	} else {
		lineageMap = raw
	}

	if v, ok := lineageMap["version"].(string); ok && version == "" {
		version = v
	}

	// Sources
	rawSources := lineageMap["sources"]
	if rawSources == nil {
		rawSources = lineageMap["source"]
	}
	if rawSources == nil {
		rawSources = raw["sources"]
	}

	if sList, ok := rawSources.([]interface{}); ok {
		for _, item := range sList {
			if sMap, ok := item.(map[string]interface{}); ok {
				s := domain.LineageSource{}
				if n, ok := sMap["name"].(string); ok {
					s.Name = n
				}
				if ds, ok := sMap["dataset"].(string); ok {
					s.Dataset = ds
				}
				if u, ok := sMap["url"].(string); ok {
					s.URL = u
				}
				if h, ok := sMap["hash"].(string); ok {
					s.Hash = h
				}
				sources = append(sources, s)

				p := s.Dataset
				if p == "" {
					p = s.Name
				}
				if p != "" && p != id {
					derivedFrom = append(derivedFrom, p)
				}
			} else if sStr, ok := item.(string); ok {
				sources = append(sources, domain.LineageSource{Name: sStr, Dataset: sStr})
				if sStr != id {
					derivedFrom = append(derivedFrom, sStr)
				}
			}
		}
	}

	// Transformations
	rawTransforms := lineageMap["transformations"]
	if rawTransforms == nil {
		rawTransforms = lineageMap["activities"]
	}
	if tList, ok := rawTransforms.([]interface{}); ok {
		for _, item := range tList {
			if tMap, ok := item.(map[string]interface{}); ok {
				t := domain.LineageTransformation{
					Type: "script",
				}
				if tool, ok := tMap["tool"].(string); ok {
					t.Tool = tool
				}
				if tp, ok := tMap["type"].(string); ok {
					t.Type = tp
				}
				if h, ok := tMap["hash"].(string); ok {
					t.Hash = h
				}
				if desc, ok := tMap["description"].(string); ok {
					t.Description = desc
				}
				if q, ok := tMap["query"].(string); ok {
					t.Query = q
				}
				transformations = append(transformations, t)
			}
		}
	}

	// WasDerivedFrom explicit
	if dwf, ok := lineageMap["was_derived_from"].([]interface{}); ok {
		for _, item := range dwf {
			if str, ok := item.(string); ok && str != id {
				derivedFrom = append(derivedFrom, str)
			}
		}
	}

	return &domain.LineageInfo{
		DatasetID:       id,
		Title:           title,
		Version:         version,
		Sources:         sources,
		Transformations: transformations,
		WasDerivedFrom:  derivedFrom,
	}
}

// BuildGraph scans the requested search directories and builds a LineageGraph DAG.
func (uc *LineageUseCase) BuildGraph(ctx context.Context, searchDirs []string, catalogURL string) (*domain.LineageGraph, error) {
	graph := domain.NewLineageGraph()
	dirs := searchDirs
	if len(dirs) == 0 {
		dirs = uc.defaultSearchDirs
	}

	for _, d := range dirs {
		if fi, err := os.Stat(d); err == nil && fi.IsDir() {
			_ = filepath.WalkDir(d, func(path string, dEntry fs.DirEntry, walkErr error) error {
				if walkErr != nil || dEntry.IsDir() {
					return nil
				}
				name := strings.ToLower(dEntry.Name())
				if name == "datapackage.yaml" || name == "datapackage.yml" || name == "datapackage.json" || name == "index.md" {
					info, err := uc.ExtractFromFile(path)
					if err == nil && info != nil && info.DatasetID != "" {
						graph.Records[info.DatasetID] = *info
					}
				}
				return nil
			})
		}
	}

	// Build nodes and edges
	for dsID, rec := range graph.Records {
		graph.Nodes[dsID] = domain.LineageNode{
			ID:    dsID,
			Title: rec.Title,
			Type:  "dataset",
		}
	}

	for dsID, rec := range graph.Records {
		var firstTrans *domain.LineageTransformation
		var label string
		if len(rec.Transformations) > 0 {
			firstTrans = &rec.Transformations[0]
			label = firstTrans.Description
			if label == "" {
				label = firstTrans.Tool
			}
		}

		for _, p := range rec.WasDerivedFrom {
			if _, exists := graph.Nodes[p]; !exists {
				nodeType := "dataset"
				if strings.HasPrefix(p, "http://") || strings.HasPrefix(p, "https://") {
					nodeType = "external_source"
				}
				graph.Nodes[p] = domain.LineageNode{
					ID:    p,
					Title: p,
					Type:  nodeType,
				}
			}

			graph.Edges = append(graph.Edges, domain.LineageEdge{
				Source:         p,
				Target:         dsID,
				Label:          label,
				Transformation: firstTrans,
			})
		}
	}

	return graph, nil
}

// GetLineage retrieves the lineage record and graph context for targetID.
func (uc *LineageUseCase) GetLineage(ctx context.Context, target string, searchDirs []string, catalogURL string) (map[string]interface{}, error) {
	// If target is a file, try extracting directly
	var directRecord *domain.LineageInfo
	targetID := target
	if fi, err := os.Stat(target); err == nil && !fi.IsDir() {
		directRecord, _ = uc.ExtractFromFile(target)
		if directRecord != nil {
			targetID = directRecord.DatasetID
		}
	}

	graph, err := uc.BuildGraph(ctx, searchDirs, catalogURL)
	if err != nil {
		return nil, err
	}

	if directRecord != nil {
		graph.Records[directRecord.DatasetID] = *directRecord
		graph.Nodes[directRecord.DatasetID] = domain.LineageNode{
			ID:    directRecord.DatasetID,
			Title: directRecord.Title,
			Type:  "dataset",
		}
	}

	upstream := graph.Upstream(targetID)
	downstream := graph.Downstream(targetID)
	rec := graph.Records[targetID]

	title := rec.Title
	if title == "" {
		if node, ok := graph.Nodes[targetID]; ok {
			title = node.Title
		} else {
			title = targetID
		}
	}

	return map[string]interface{}{
		"dataset_id":      targetID,
		"title":           title,
		"version":         rec.Version,
		"upstream":        upstream,
		"downstream":      downstream,
		"sources":         rec.Sources,
		"transformations": rec.Transformations,
		"mermaid":         graph.ToMermaid(targetID),
		"ascii":           graph.ToASCII(targetID),
		"graph":           graph,
	}, nil
}
