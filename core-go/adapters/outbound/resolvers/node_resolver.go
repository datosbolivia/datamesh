package resolvers

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/manifests"
	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// NodeDataProductResolver fetches and parses OKF v0.2 Markdown files and package manifests.
type NodeDataProductResolver struct {
	httpClient *http.Client
}

// NewNodeDataProductResolver initializes the node resolver.
func NewNodeDataProductResolver(timeout time.Duration) *NodeDataProductResolver {
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	return &NodeDataProductResolver{
		httpClient: &http.Client{Timeout: timeout},
	}
}

// FetchDataProduct retrieves node data (index.md, datapackage.json/yaml/yml, or node directory)
// and constructs a DataProduct aggregate.
func (r *NodeDataProductResolver) FetchDataProduct(ctx context.Context, resolvedURL string) (*domain.DataProduct, error) {
	reader := manifests.NewUnifiedMetadataReader("", r.httpClient.Timeout)
	lower := strings.ToLower(resolvedURL)
	if strings.HasSuffix(lower, ".json") || strings.HasSuffix(lower, ".yaml") || strings.HasSuffix(lower, ".yml") || !strings.HasSuffix(lower, ".md") {
		return reader.ReadNode(ctx, resolvedURL)
	}

	raw, err := r.readContent(ctx, resolvedURL)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch node at %s: %w", resolvedURL, err)
	}

	manifest, desc, err := manifests.ParseOKFFrontmatter([]byte(raw))
	if err != nil {
		return nil, fmt.Errorf("failed to parse OKF frontmatter: %w", err)
	}

	dp, err := domain.NewDataProduct(resolvedURL, manifest, desc, nil)
	if err != nil {
		return nil, err
	}
	dp.RawContent = raw
	return dp, nil
}

func (r *NodeDataProductResolver) readContent(ctx context.Context, targetURL string) (string, error) {
	if strings.HasPrefix(targetURL, "file://") {
		localPath := strings.TrimPrefix(targetURL, "file://")
		data, err := os.ReadFile(localPath)
		return string(data), err
	}

	if !strings.HasPrefix(targetURL, "http://") && !strings.HasPrefix(targetURL, "https://") {
		// Treat as local file path
		data, err := os.ReadFile(targetURL)
		return string(data), err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, targetURL, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "datamesh-sdk/0.2 (Go-Core)")

	resp, err := r.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("HTTP error %d %s", resp.StatusCode, resp.Status)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	return string(body), nil
}

