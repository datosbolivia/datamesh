package domain

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
)

var (
	ErrInvalidTriadFormat = errors.New("invalid triad format: expected '[catalog:]dataset:resource' or 'datamesh://[catalog/]dataset/resource'")
	tableRefSQLRegex      = regexp.MustCompile(`(?i)\b(?:FROM|JOIN)\s+(?:ONLY\s+)?(?:["']([^"']+)["']|([a-zA-Z0-9_\-\.:/]+))`)
	quotedColonRegex      = regexp.MustCompile(`["']([^"':\s]+:[^"']+)["']`)
)

// ResourceTriad represents the canonical address '[catalog:]dataset:resource' in the federated DataMesh.
type ResourceTriad struct {
	Catalog  string `json:"catalog,omitempty"`
	Dataset  string `json:"dataset"`
	Resource string `json:"resource"`
}

// String returns the canonical triad string representation.
func (t ResourceTriad) String() string {
	if t.Catalog != "" {
		return fmt.Sprintf("%s:%s:%s", t.Catalog, t.Dataset, t.Resource)
	}
	return fmt.Sprintf("%s:%s", t.Dataset, t.Resource)
}

// FullURI returns the URI representation with datamesh:// scheme.
func (t ResourceTriad) FullURI() string {
	if t.Catalog != "" {
		return fmt.Sprintf("datamesh://%s/%s/%s", t.Catalog, t.Dataset, t.Resource)
	}
	return fmt.Sprintf("datamesh://%s/%s", t.Dataset, t.Resource)
}

// ParseTriad parses a string in 'catalogo:dataset:resource', 'dataset:resource',
// or 'datamesh://[catalogo/]dataset/resource' format into a ResourceTriad.
func ParseTriad(raw string) (*ResourceTriad, error) {
	trimmed := strings.Trim(strings.TrimSpace(raw), "\"'`")
	if trimmed == "" {
		return nil, ErrInvalidTriadFormat
	}

	// 1. datamesh:// URI scheme
	if strings.HasPrefix(trimmed, "datamesh://") {
		clean := strings.TrimPrefix(trimmed, "datamesh://")
		parts := strings.Split(clean, "/")
		if len(parts) == 3 {
			return &ResourceTriad{
				Catalog:  strings.TrimSpace(parts[0]),
				Dataset:  strings.TrimSpace(parts[1]),
				Resource: strings.TrimSpace(parts[2]),
			}, nil
		} else if len(parts) == 2 {
			return &ResourceTriad{
				Dataset:  strings.TrimSpace(parts[0]),
				Resource: strings.TrimSpace(parts[1]),
			}, nil
		}
		return nil, ErrInvalidTriadFormat
	}

	// 2. Colon-separated format
	if strings.Contains(trimmed, ":") {
		parts := strings.Split(trimmed, ":")
		if len(parts) == 3 {
			cat := strings.TrimSpace(parts[0])
			ds := strings.TrimSpace(parts[1])
			res := strings.TrimSpace(parts[2])
			if ds == "" || res == "" {
				return nil, ErrInvalidTriadFormat
			}
			return &ResourceTriad{
				Catalog:  cat,
				Dataset:  ds,
				Resource: res,
			}, nil
		} else if len(parts) == 2 {
			ds := strings.TrimSpace(parts[0])
			res := strings.TrimSpace(parts[1])
			if ds == "" || res == "" {
				return nil, ErrInvalidTriadFormat
			}
			return &ResourceTriad{
				Dataset:  ds,
				Resource: res,
			}, nil
		}
	}

	return nil, ErrInvalidTriadFormat
}

// ExtractTriadsFromSQL finds all table references formatted as triads or datamesh URIs inside a SQL statement.
func ExtractTriadsFromSQL(sqlQuery string) []ResourceTriad {
	var triads []ResourceTriad
	seen := make(map[string]bool)

	// 1. Scan FROM and JOIN clauses
	matches := tableRefSQLRegex.FindAllStringSubmatch(sqlQuery, -1)
	for _, m := range matches {
		rawRef := m[1]
		if rawRef == "" {
			rawRef = m[2]
		}
		rawRef = strings.TrimSpace(rawRef)
		if rawRef == "" {
			continue
		}

		if triad, err := ParseTriad(rawRef); err == nil {
			key := triad.String()
			if !seen[key] {
				seen[key] = true
				triads = append(triads, *triad)
			}
		}
	}

	// 2. Scan quoted strings with colons
	quotedMatches := quotedColonRegex.FindAllStringSubmatch(sqlQuery, -1)
	for _, m := range quotedMatches {
		if len(m) > 1 {
			rawRef := strings.TrimSpace(m[1])
			if triad, err := ParseTriad(rawRef); err == nil {
				key := triad.String()
				if !seen[key] {
					seen[key] = true
					triads = append(triads, *triad)
				}
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
