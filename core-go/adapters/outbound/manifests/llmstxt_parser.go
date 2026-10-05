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
	entryRegex      = regexp.MustCompile(`^-\s*\[(.*?)\]\((.*?)\)(?::\s*(.*))?$`)
	domainRegex     = regexp.MustCompile(`\(Dominio:\s*([^)]*?)(?:\.|\)|Recursos:)`)
	recRegex        = regexp.MustCompile(`Recursos:\s*([^)]+)\)`)
	reqHeaderRegex  = regexp.MustCompile(`^###\s*\[(.*?)\]\s*(.*?)(?:\s*\((?:Institución|Agencia):\s*([^)]+)\))?$`)
	bulletItemRegex = regexp.MustCompile(`^\s*[*+-]\s*\[(.*?)\]\s*(.*)`)
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
