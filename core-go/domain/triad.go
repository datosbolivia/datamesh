package domain

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
)

var (
	ErrInvalidTriadFormat = errors.New("invalid triad format: expected 'catalogo:dataset:resource'")
	triadRegex            = regexp.MustCompile(`["']?([a-zA-Z0-9_\-\.]+):([a-zA-Z0-9_\-\.]+):([a-zA-Z0-9_\-\.]+)["']?`)
)

// ResourceTriad represents the canonical address 'catalogo:dataset:resource' in the federated DataMesh.
type ResourceTriad struct {
	Catalog  string `json:"catalog"`
	Dataset  string `json:"dataset"`
	Resource string `json:"resource"`
}

// String returns the canonical triad string representation.
func (t ResourceTriad) String() string {
	return fmt.Sprintf("%s:%s:%s", t.Catalog, t.Dataset, t.Resource)
}

// ParseTriad parses a string in 'catalogo:dataset:resource' format into a ResourceTriad.
func ParseTriad(raw string) (*ResourceTriad, error) {
	trimmed := strings.Trim(strings.TrimSpace(raw), "\"'`")
	parts := strings.Split(trimmed, ":")
	if len(parts) != 3 {
		return nil, ErrInvalidTriadFormat
	}

	cat := strings.TrimSpace(parts[0])
	ds := strings.TrimSpace(parts[1])
	res := strings.TrimSpace(parts[2])

	if cat == "" || ds == "" || res == "" {
		return nil, ErrInvalidTriadFormat
	}

	return &ResourceTriad{
		Catalog:  cat,
		Dataset:  ds,
		Resource: res,
	}, nil
}

// ExtractTriadsFromSQL finds all table references formatted as 'catalogo:dataset:resource' inside a SQL statement.
func ExtractTriadsFromSQL(sqlQuery string) []ResourceTriad {
	matches := triadRegex.FindAllStringSubmatch(sqlQuery, -1)
	var triads []ResourceTriad
	seen := make(map[string]bool)

	for _, m := range matches {
		if len(m) >= 4 {
			triad := ResourceTriad{
				Catalog:  m[1],
				Dataset:  m[2],
				Resource: m[3],
			}
			key := triad.String()
			if !seen[key] {
				seen[key] = true
				triads = append(triads, triad)
			}
		}
	}
	return triads
}

// ResolvedResource specifies the concrete physical file, URL, and tabular format of a resolved triad.
type ResolvedResource struct {
	Triad       ResourceTriad `json:"triad"`
	PhysicalURI string        `json:"physical_uri"`
	Format      string        `json:"format"` // "parquet", "csv", "json", "tsv"
}
