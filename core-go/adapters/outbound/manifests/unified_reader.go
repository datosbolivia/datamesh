package manifests

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// UnifiedMetadataReader coordinates heterogeneous manifest parsers (JSON, YAML, Markdown, LLMs.txt)
// and implements both UnifiedMetadataReaderPort and TriadResolverPort.
type UnifiedMetadataReader struct {
	parsers    []outbound.ManifestParserPort
	httpClient *http.Client
	catalogURL string
}

// NewUnifiedMetadataReader initializes the reader with standard parsers.
func NewUnifiedMetadataReader(catalogURL string, timeout time.Duration) *UnifiedMetadataReader {
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	r := &UnifiedMetadataReader{
		httpClient: &http.Client{Timeout: timeout},
		catalogURL: catalogURL,
	}

	// Register built-in standard parsers
	r.RegisterParser(NewDataPackageJSONParser())
	r.RegisterParser(NewDataPackageYAMLParser())
	r.RegisterParser(NewOKFMarkdownParser())
	r.RegisterParser(NewLLMSTxtParser())

	return r
}

// RegisterParser dynamically adds or extends support for manifest formats (DCAT, RO-Crate, etc.).
func (r *UnifiedMetadataReader) RegisterParser(parser outbound.ManifestParserPort) {
	r.parsers = append(r.parsers, parser)
}

// ReadPackage reads and parses a manifest file from a local path or HTTP URL.
func (r *UnifiedMetadataReader) ReadPackage(ctx context.Context, uriOrPath string) (*domain.PackageManifest, error) {
	data, err := r.readData(ctx, uriOrPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read manifest from %s: %w", uriOrPath, err)
	}

	for _, p := range r.parsers {
		if p.CanParse(uriOrPath, data) {
			return p.ParseManifest(ctx, data, uriOrPath)
		}
	}

	return nil, fmt.Errorf("no manifest parser found capable of parsing %s", uriOrPath)
}

// ReadNode resolves a node directory or index.md and returns a unified DataProduct with resources.
func (r *UnifiedMetadataReader) ReadNode(ctx context.Context, uriOrPath string) (*domain.DataProduct, error) {
	baseDir := uriOrPath
	if strings.HasSuffix(baseDir, ".md") || strings.HasSuffix(baseDir, ".json") || strings.HasSuffix(baseDir, ".yaml") || strings.HasSuffix(baseDir, ".yml") {
		baseDir = filepath.Dir(baseDir)
	}

	// 1. Read index.md for frontmatter and descriptions
	indexPath := filepath.Join(baseDir, "index.md")
	var manifest domain.Manifest
	var description string
	var rawContent string

	if data, err := r.readData(ctx, indexPath); err == nil {
		rawContent = string(data)
		m, desc, err := ParseOKFFrontmatter(data)
		if err == nil {
			manifest = m
			description = desc
		}
	}

	// 2. Discover package manifest (datapackage.json, datapackage.yaml, datapackage.yml)
	var resources []domain.Resource
	candidateFiles := []string{
		"datapackage.json",
		"datapackage.yaml",
		"datapackage.yml",
	}

	for _, fname := range candidateFiles {
		targetP := filepath.Join(baseDir, fname)
		if pkg, err := r.ReadPackage(ctx, targetP); err == nil {
			resources = pkg.Resources
			if manifest.Title == "" && pkg.Title != "" {
				manifest.Title = pkg.Title
			}
			break
		}
	}

	if manifest.Title == "" {
		manifest.Title = filepath.Base(baseDir)
	}
	if manifest.Type == "" {
		manifest.Type = "dataset"
	}
	if len(manifest.Dimensions) == 0 {
		manifest.Dimensions = []string{"core"}
	}

	dp, err := domain.NewDataProduct(uriOrPath, manifest, description, resources)
	if err != nil {
		return nil, err
	}
	dp.RawContent = rawContent
	return dp, nil
}

// ReadCatalog fetches and parses a federated catalog (llms.txt).
func (r *UnifiedMetadataReader) ReadCatalog(ctx context.Context, uriOrPath string) (*domain.Catalog, error) {
	target := uriOrPath
	if target == "" {
		target = r.catalogURL
	}
	data, err := r.readData(ctx, target)
	if err != nil {
		return nil, err
	}

	parser := NewLLMSTxtParser()
	return parser.ParseCatalog(data, target)
}

// ResolveTriad resolves a canonical 'catalogo:dataset:resource' or 'dataset:resource' triad to physical URL and format.
func (r *UnifiedMetadataReader) ResolveTriad(ctx context.Context, triad domain.ResourceTriad) (*domain.ResolvedResource, error) {
	dataset := triad.Dataset
	resourceName := triad.Resource

	// 1. Search candidate local node directories
	candidateDirs := []string{
		filepath.Join("knowledge", "nodes", dataset),
		filepath.Join("nodes", dataset),
		filepath.Join("..", "catalogo-datamesh", "knowledge", "nodes", dataset),
	}

	for _, dir := range candidateDirs {
		for _, fname := range []string{"datapackage.json", "datapackage.yaml", "datapackage.yml"} {
			fullP := filepath.Join(dir, fname)
			if pkg, err := r.ReadPackage(ctx, fullP); err == nil {
				if res, found := pkg.FindResource(resourceName); found {
					return &domain.ResolvedResource{
						Triad:       triad,
						PhysicalURI: res.Path,
						Format:      res.Format,
					}, nil
				}
			}
		}
	}

	// 2. Search catalog entries via HTTP discovery
	if r.catalogURL != "" {
		if cat, err := r.ReadCatalog(ctx, r.catalogURL); err == nil {
			cleanDs := strings.ToLower(dataset)
			for _, entry := range cat.Entries {
				u := strings.ToLower(entry.URI)
				rUrl := strings.ToLower(entry.ResolvedURL)
				t := strings.ToLower(entry.Title)
				if strings.Contains(u, cleanDs) || strings.Contains(rUrl, cleanDs) || t == cleanDs || domain.Slugify(t) == cleanDs {
					baseDir := entry.ResolvedURL
					if idx := strings.LastIndex(baseDir, "/"); idx != -1 {
						baseDir = baseDir[:idx]
					}

					for _, fname := range []string{"datapackage.json", "datapackage.yaml", "datapackage.yml"} {
						dpURL := fmt.Sprintf("%s/%s", baseDir, fname)
						if pkg, err := r.ReadPackage(ctx, dpURL); err == nil {
							if res, found := pkg.FindResource(resourceName); found {
								return &domain.ResolvedResource{
									Triad:       triad,
									PhysicalURI: res.Path,
									Format:      res.Format,
								}, nil
							}
						}
					}
				}
			}
		}
	}

	// 3. Fallback to resource name directly
	return &domain.ResolvedResource{
		Triad:       triad,
		PhysicalURI: resourceName,
		Format:      inferFormatFromPath(resourceName),
	}, nil
}

func (r *UnifiedMetadataReader) readData(ctx context.Context, target string) ([]byte, error) {
	if strings.HasPrefix(target, "file://") {
		return os.ReadFile(strings.TrimPrefix(target, "file://"))
	}
	if !strings.HasPrefix(target, "http://") && !strings.HasPrefix(target, "https://") {
		return os.ReadFile(target)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "datamesh-sdk/0.2 (Go-Core Unified Reader)")

	resp, err := r.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d %s", resp.StatusCode, resp.Status)
	}

	return io.ReadAll(resp.Body)
}
