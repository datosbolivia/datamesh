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
// Example standard: - [Title](/raw/nodes/...): Description. (Dominio: Finanzas. Recursos: r1, r2)
// Example hierarchical: ### [REQ-01] Title \n * [REQ_01_A] Title (Tríada: `...`): /raw/path
var (
	entryRegex      = regexp.MustCompile(`^-\s*\[(.*?)\]\((.*?)\)(?::\s*(.*))?$`)
	domainRegex     = regexp.MustCompile(`\(Dominio:\s*([^)]*?)(?:\.|\)|Recursos:)`)
	recRegex        = regexp.MustCompile(`Recursos:\s*([^)]+)\)`)
	reqHeaderRegex  = regexp.MustCompile(`^###\s*\[(.*?)\]\s*(.*?)(?:\s*\((?:Institución|Agencia):\s*([^)]+)\))?$`)
	triadRegex      = regexp.MustCompile(`Tríada:\s*` + "`" + `([^` + "`" + `]+)` + "`")
	bulletItemRegex = regexp.MustCompile(`^\s*[*+-]\s*\[(.*?)\]\s*(.*)`)
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

	type currentReqInfo struct {
		id          string
		title       string
		institution string
		domain      string
		specURI     string
	}
	var currentReq *currentReqInfo

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

		// 1. Check for Requirement / Section Header: ### [REQ-01] Title (Institución: ...)
		if rm := reqHeaderRegex.FindStringSubmatch(line); len(rm) > 2 {
			inst := ""
			if len(rm) > 3 {
				inst = strings.TrimSpace(rm[3])
			}
			currentReq = &currentReqInfo{
				id:          strings.TrimSpace(rm[1]),
				title:       strings.TrimSpace(rm[2]),
				institution: inst,
			}
			continue
		}

		// If within a requirement block, inspect metadata and child components
		if currentReq != nil {
			if strings.HasPrefix(line, "- Dominio Temático:") {
				parts := strings.SplitN(line, ":", 2)
				if len(parts) == 2 {
					currentReq.domain = strings.TrimSpace(parts[1])
				}
				continue
			}
			if strings.HasPrefix(line, "- Especificación Técnica:") {
				parts := strings.SplitN(line, ":", 2)
				if len(parts) == 2 {
					currentReq.specURI = strings.TrimSpace(parts[1])
				}
				continue
			}

			// Check hierarchical bullet: * [REQ_01_A] Title (Tríada: `...`, ...): /raw/path.md
			if (strings.HasPrefix(line, "* [") || strings.HasPrefix(line, "- [")) && strings.Contains(line, ":") {
				lastColon := strings.LastIndex(line, ":")
				compURI := strings.TrimSpace(line[lastColon+1:])
				if strings.HasPrefix(compURI, "/") || strings.HasPrefix(compURI, "http://") || strings.HasPrefix(compURI, "https://") || strings.HasSuffix(compURI, ".md") {
					prefix := strings.TrimSpace(line[:lastColon])
					if bm := bulletItemRegex.FindStringSubmatch(prefix); len(bm) > 2 {
						compID := strings.TrimSpace(bm[1])
						rest := strings.TrimSpace(bm[2])

						titleClean := rest
						metaClean := ""
						if idx := strings.Index(rest, "(Tríada:"); idx != -1 {
							titleClean = strings.TrimSpace(rest[:idx])
							metaClean = strings.TrimSpace(rest[idx+1:])
							metaClean = strings.TrimSuffix(metaClean, ")")
						} else if idx := strings.Index(rest, "(Dominio:"); idx != -1 {
							titleClean = strings.TrimSpace(rest[:idx])
							metaClean = strings.TrimSpace(rest[idx+1:])
							metaClean = strings.TrimSuffix(metaClean, ")")
						}

						resolvedURL := resolveURL(parsedBase, compURI)
						fullTitle := fmt.Sprintf("[%s] %s", currentReq.id, titleClean)
						desc := fmt.Sprintf("%s (%s). %s", titleClean, currentReq.title, metaClean)

						catalog.Entries = append(catalog.Entries, domain.CatalogEntry{
							Title:       fullTitle,
							URI:         compURI,
							ResolvedURL: resolvedURL,
							Description: strings.TrimSpace(desc),
							Domain:      currentReq.domain,
							Resources:   []string{strings.ToLower(compID)},
						})
						continue
					}
				}
			}
		}

		// 2. Standard Flat llms.txt entry: - [Title](rawURI): desc
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
