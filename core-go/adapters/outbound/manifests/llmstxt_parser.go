package manifests

import (
	"bufio"
	"bytes"
	"context"
	"net/url"
	"regexp"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

var (
	entryRegex  = regexp.MustCompile(`^-\s*\[(.*?)\]\((.*?)\)(?::\s*(.*))?$`)
	domainRegex = regexp.MustCompile(`\(Dominio:\s*([^)]*?)(?:\.|\)|Recursos:)`)
	recRegex    = regexp.MustCompile(`Recursos:\s*([^)]+)\)`)
)

// LLMSTxtParser parses llms.txt, llm.txt, and llms-full.txt federated catalogs.
type LLMSTxtParser struct{}

func NewLLMSTxtParser() *LLMSTxtParser {
	return &LLMSTxtParser{}
}

func (p *LLMSTxtParser) Name() string {
	return "llms-txt"
}

func (p *LLMSTxtParser) CanParse(filenameOrURL string, data []byte) bool {
	lower := strings.ToLower(filenameOrURL)
	if strings.HasSuffix(lower, "llms.txt") || strings.HasSuffix(lower, "llm.txt") || strings.HasSuffix(lower, "llms-full.txt") {
		return true
	}
	content := string(data)
	return strings.Contains(content, "# ") && strings.Contains(content, "- [")
}

func (p *LLMSTxtParser) ParseManifest(ctx context.Context, data []byte, baseURL string) (*domain.PackageManifest, error) {
	cat, err := p.ParseCatalog(data, baseURL)
	if err != nil {
		return nil, err
	}

	return &domain.PackageManifest{
		Title:       cat.Title,
		Description: cat.Description,
		Format:      domain.PackageFormatLLMSTxt,
		Resources:   make([]domain.Resource, 0),
		Metadata: map[string]interface{}{
			"source_url": cat.SourceURL,
			"entries":    cat.Entries,
		},
	}, nil
}

func (p *LLMSTxtParser) ParseCatalog(data []byte, sourceURL string) (*domain.Catalog, error) {
	scanner := bufio.NewScanner(bytes.NewReader(data))
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

		if matches := entryRegex.FindStringSubmatch(line); len(matches) > 2 {
			title := strings.TrimSpace(matches[1])
			rawURI := strings.TrimSpace(matches[2])
			descText := ""
			if len(matches) > 3 {
				descText = strings.TrimSpace(matches[3])
			}

			resolvedURL := resolveURL(parsedBase, rawURI)

			domainName := ""
			if dMatches := domainRegex.FindStringSubmatch(descText); len(dMatches) > 1 {
				domainName = strings.TrimSpace(dMatches[1])
			}

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
