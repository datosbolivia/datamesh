package manifests

import (
	"context"
	"encoding/json"
	"net/url"
	"path/filepath"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// DataPackageJSONParser parses Frictionless DataPackage manifests formatted in JSON.
type DataPackageJSONParser struct{}

func NewDataPackageJSONParser() *DataPackageJSONParser {
	return &DataPackageJSONParser{}
}

func (p *DataPackageJSONParser) Name() string {
	return "datapackage-json"
}

func (p *DataPackageJSONParser) CanParse(filenameOrURL string, data []byte) bool {
	lower := strings.ToLower(filenameOrURL)
	if strings.HasSuffix(lower, "datapackage.json") {
		return true
	}
	trimmed := strings.TrimSpace(string(data))
	return strings.HasPrefix(trimmed, "{") && strings.Contains(trimmed, `"resources"`)
}

type rawJSONDataPackage struct {
	Name        string            `json:"name"`
	Title       string            `json:"title"`
	Description string            `json:"description"`
	Version     string            `json:"version"`
	Resources   []rawJSONResource `json:"resources"`
}

type rawJSONResource struct {
	Name       string `json:"name"`
	Path       string `json:"path"`
	Format     string `json:"format"`
	MediaType  string `json:"mediatype"`
	Bytes      int64  `json:"bytes"`
	BytesCount int64  `json:"bytes_count"`
	Hash       string `json:"hash"`
	HashSHA256 string `json:"hash_sha256"`
}

func (p *DataPackageJSONParser) ParseManifest(ctx context.Context, data []byte, baseURL string) (*domain.PackageManifest, error) {
	var raw rawJSONDataPackage
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}

	var parsedResources []domain.Resource
	for _, r := range raw.Resources {
		fmtStr := strings.ToLower(strings.TrimSpace(r.Format))
		if fmtStr == "" {
			fmtStr = inferFormatFromPath(r.Path)
		}

		resolvedPath := resolveResourcePath(baseURL, r.Path)

		bytesCount := r.BytesCount
		if bytesCount == 0 {
			bytesCount = r.Bytes
		}

		sha := r.HashSHA256
		if sha == "" {
			sha = r.Hash
		}

		parsedResources = append(parsedResources, domain.Resource{
			Name:       r.Name,
			Path:       resolvedPath,
			Format:     fmtStr,
			BytesCount: bytesCount,
			HashSHA256: sha,
		})
	}

	return &domain.PackageManifest{
		Name:        raw.Name,
		Title:       raw.Title,
		Description: raw.Description,
		Format:      domain.PackageFormatDataPackageJSON,
		Version:     raw.Version,
		Resources:   parsedResources,
	}, nil
}

func inferFormatFromPath(path string) string {
	clean := strings.TrimSpace(path)
	if idx := strings.Index(clean, "?"); idx != -1 {
		clean = clean[:idx]
	}
	ext := strings.ToLower(filepath.Ext(clean))
	switch ext {
	case ".parquet", ".pq":
		return "parquet"
	case ".tsv":
		return "tsv"
	case ".json":
		return "json"
	case ".jsonl":
		return "jsonl"
	default:
		return "csv"
	}
}

func resolveResourcePath(baseURL, targetPath string) string {
	clean := strings.TrimSpace(targetPath)
	if clean == "" {
		return ""
	}
	if strings.HasPrefix(clean, "http://") || strings.HasPrefix(clean, "https://") || strings.HasPrefix(clean, "file://") {
		return clean
	}
	if baseURL == "" {
		return clean
	}

	if strings.HasPrefix(baseURL, "http://") || strings.HasPrefix(baseURL, "https://") {
		base, err := url.Parse(baseURL)
		if err == nil {
			ref, err := url.Parse(clean)
			if err == nil {
				return base.ResolveReference(ref).String()
			}
		}
	}

	// Local file path
	baseDir := filepath.Dir(baseURL)
	return filepath.Join(baseDir, clean)
}
