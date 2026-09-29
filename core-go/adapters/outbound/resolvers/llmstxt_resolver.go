package resolvers

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// Regex patterns to parse llms.txt entries
// Example: - [Title](/raw/nodes/...): Description. (Dominio: Finanzas. Recursos: r1, r2)
var (
	entryRegex  = regexp.MustCompile(`^-\s*\[(.*?)\]\((.*?)\)(?::\s*(.*))?$`)
	domainRegex = regexp.MustCompile(`\(Dominio:\s*([^)]*?)(?:\.|\)|Recursos:)`)
	recRegex    = regexp.MustCompile(`Recursos:\s*([^)]+)\)`)
)

// LLMSTxtCatalogResolver resolves federated catalogs formatted as llms.txt.
type LLMSTxtCatalogResolver struct {
	httpClient *http.Client
}

// NewLLMSTxtCatalogResolver initializes the HTTP resolver with timeout.
func NewLLMSTxtCatalogResolver(timeout time.Duration) *LLMSTxtCatalogResolver {
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	return &LLMSTxtCatalogResolver{
		httpClient: &http.Client{Timeout: timeout},
	}
}

// FetchCatalog downloads and parses llms.txt, creating a domain.Catalog instance.
func (r *LLMSTxtCatalogResolver) FetchCatalog(ctx context.Context, catalogURL string) (*domain.Catalog, error) {
	content, err := r.readContent(ctx, catalogURL)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch catalog from %s: %w", catalogURL, err)
	}

	return r.parseLLMSTxt(content, catalogURL)
}

func (r *LLMSTxtCatalogResolver) readContent(ctx context.Context, targetURL string) (string, error) {
	if strings.HasPrefix(targetURL, "file://") {
		localPath := strings.TrimPrefix(targetURL, "file://")
		data, err := os.ReadFile(localPath)
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

func (r *LLMSTxtCatalogResolver) parseLLMSTxt(content, sourceURL string) (*domain.Catalog, error) {
	scanner := bufio.NewScanner(strings.NewReader(content))
	catalog := &domain.Catalog{
		SourceURL: sourceURL,
		Entries:   make([]domain.CatalogEntry, 0),
	}

	parsedBase, _ := url.Parse(sourceURL)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}

		if strings.HasPrefix(line, "# ") && catalog.Title == "" {
			catalog.Title = strings.TrimPrefix(line, "# ")
			continue
		}

		if strings.HasPrefix(line, "> ") && catalog.Description == "" {
			catalog.Description = strings.TrimPrefix(line, "> ")
			continue
		}

		// Check for dataset items
		if matches := entryRegex.FindStringSubmatch(line); len(matches) > 2 {
			title := strings.TrimSpace(matches[1])
			rawURI := strings.TrimSpace(matches[2])
			descText := ""
			if len(matches) > 3 {
				descText = strings.TrimSpace(matches[3])
			}

			resolvedURL := resolveURL(parsedBase, rawURI)

			// Extract Domain if present
			domainName := ""
			if dMatches := domainRegex.FindStringSubmatch(descText); len(dMatches) > 1 {
				domainName = strings.TrimSpace(dMatches[1])
			}

			// Extract Resources if present
			var resources []string
			if rMatches := recRegex.FindStringSubmatch(descText); len(rMatches) > 1 {
				rawRecs := strings.Split(rMatches[1], ",")
				for _, rec := range rawRecs {
					tr := strings.TrimSpace(rec)
					if tr != "" {
						resources = append(resources, tr)
					}
				}
			}

			// Clean description
			cleanDesc := descText
			if idx := strings.Index(cleanDesc, "(Dominio:"); idx != -1 {
				cleanDesc = strings.TrimSpace(cleanDesc[:idx])
			}

			catalog.Entries = append(catalog.Entries, domain.CatalogEntry{
				Title:       title,
				URI:         rawURI,
				ResolvedURL: resolvedURL,
				Description: cleanDesc,
				Domain:      domainName,
				Resources:   resources,
			})
		}
	}

	return catalog, scanner.Err()
}

func resolveURL(base *url.URL, ref string) string {
	if base == nil {
		return ref
	}
	refURL, err := url.Parse(ref)
	if err != nil {
		return ref
	}
	return base.ResolveReference(refURL).String()
}
