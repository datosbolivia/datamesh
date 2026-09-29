package domain

import (
	"strings"
)

// CatalogEntry represents a reference to a federated OKF Data Product in llms.txt.
type CatalogEntry struct {
	Title         string   `json:"title"`
	URI           string   `json:"uri"`
	ResolvedURL   string   `json:"resolved_url"`
	Description   string   `json:"description"`
	Domain        string   `json:"domain"`
	Resources     []string `json:"resources"`
	CatalogSource string   `json:"catalog_source,omitempty"`
}

// Catalog represents a collection of Data Products discovered from one or more sovereign catalogs.
type Catalog struct {
	Title          string         `json:"title"`
	Description    string         `json:"description"`
	SourceURL      string         `json:"source_url"`
	SourceCatalogs []string       `json:"source_catalogs,omitempty"`
	Entries        []CatalogEntry `json:"entries"`
}

// FindByKeyword searches catalog entries matching a substring in title, description, or domain.
func (c *Catalog) FindByKeyword(keyword string) []CatalogEntry {
	if keyword == "" {
		return c.Entries
	}
	kw := strings.ToLower(keyword)
	var matches []CatalogEntry

	for _, entry := range c.Entries {
		if strings.Contains(strings.ToLower(entry.Title), kw) ||
			strings.Contains(strings.ToLower(entry.Description), kw) ||
			strings.Contains(strings.ToLower(entry.Domain), kw) {
			matches = append(matches, entry)
		}
	}
	return matches
}

// FindByDomain returns catalog entries belonging to an exact or partial domain category.
func (c *Catalog) FindByDomain(domainCategory string) []CatalogEntry {
	dc := strings.ToLower(strings.TrimSpace(domainCategory))
	var matches []CatalogEntry

	for _, entry := range c.Entries {
		if strings.Contains(strings.ToLower(entry.Domain), dc) {
			matches = append(matches, entry)
		}
	}
	return matches
}
