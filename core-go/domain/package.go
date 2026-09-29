package domain

import (
	"regexp"
	"strings"
)

// PackageFormat specifies the manifest standard or syntax.
type PackageFormat string

const (
	PackageFormatDataPackageJSON PackageFormat = "datapackage-json"
	PackageFormatDataPackageYAML PackageFormat = "datapackage-yaml"
	PackageFormatOKFMarkdown     PackageFormat = "okf-markdown"
	PackageFormatLLMSTxt         PackageFormat = "llms-txt"
	PackageFormatCustom          PackageFormat = "custom"
)

// PackageManifest represents a normalized metadata package describing resources and schema.
type PackageManifest struct {
	Name        string                 `json:"name"`
	Title       string                 `json:"title,omitempty"`
	Description string                 `json:"description,omitempty"`
	Format      PackageFormat          `json:"format"`
	Version     string                 `json:"version,omitempty"`
	Resources   []Resource             `json:"resources"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// Slugify sanitizes text replacing non-alphanumeric chars with underscores.
func Slugify(text string) string {
	reg := regexp.MustCompile(`[^a-zA-Z0-9]+`)
	return strings.Trim(strings.ToLower(reg.ReplaceAllString(text, "_")), "_")
}

// FindResource locates a resource by exact name, case-insensitive name, or slug.
func (pm *PackageManifest) FindResource(nameOrSlug string) (*Resource, bool) {
	norm := strings.ToLower(strings.TrimSpace(nameOrSlug))
	slug := Slugify(nameOrSlug)
	for i := range pm.Resources {
		r := &pm.Resources[i]
		rNorm := strings.ToLower(strings.TrimSpace(r.Name))
		if rNorm == norm || Slugify(r.Name) == slug || (len(slug) > 3 && strings.Contains(rNorm, slug)) {
			return r, true
		}
	}
	return nil, false
}
