package domain

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

// FrictionlessResource mirrors a CKAN/Frictionless datapackage resource entry (ADR 0012).
type FrictionlessResource struct {
	Name     string `json:"name"`
	Path     string `json:"path,omitempty"`
	Format   string `json:"format,omitempty"`
	Mediatype string `json:"mediatype,omitempty"`
	Bytes    int64  `json:"bytes,omitempty"`
	SHA256   string `json:"hash,omitempty"`
}

// CKANDataPackageJSON mirrors the CKAN /dataset/<id>/datapackage.json bridge (ADR 0012, CU-19).
type CKANDataPackageJSON struct {
	Name        string                 `json:"name"`
	Title       string                 `json:"title,omitempty"`
	Description string                 `json:"description,omitempty"`
	Version     string                 `json:"version,omitempty"`
	Resources   []FrictionlessResource `json:"resources"`
	Extras      map[string]interface{} `json:"extras,omitempty"`
}

// DCATDistribution mirrors a W3C DCAT-AP dataset distribution (ADR 0013 export hub).
type DCATDistribution struct {
	Type       string `json:"@type"`
	Format     string `json:"dct:format,omitempty"`
	MediaType  string `json:"dcat:mediaType,omitempty"`
	AccessURL  string `json:"dcat:accessURL,omitempty"`
	ByteSize   int64  `json:"dcat:byteSize,omitempty"`
}

// DCATDatasetJSON mirrors a W3C DCAT-AP dataset for catalogs of type "dcat".
type DCATDatasetJSON struct {
	Context     string              `json:"@context"`
	Type        string              `json:"@type"`
	ID          string              `json:"@id,omitempty"`
	Title       string              `json:"dct:title"`
	Description string              `json:"dct:description,omitempty"`
	Issued      string              `json:"dct:issued,omitempty"`
	Modified    string              `json:"dct:modified,omitempty"`
	Version     string              `json:"owl:versionInfo,omitempty"`
	Keywords    []string            `json:"dcat:keyword,omitempty"`
	Theme       []string            `json:"dcat:theme,omitempty"`
	Distribution []DCATDistribution `json:"dcat:distribution,omitempty"`
}

const (
	// DCATContext is the JSON-LD context document for DCAT serialization.
	DCATContext = "https://www.w3.org/ns/dcat.jsonld"
	// CKANDataPackageProfile identifies the Frictionless/cross-storage bridge serialization.
	CKANDataPackageProfile = "ckan-datapackage"
)

// ToCKANDataPackageJSON converts an ODKF DataProduct into the CKAN-compatible Frictionless
// DataPackage serialization (ADR 0012 / CU-19), preserving resources and ODKF extras.
func (dp *DataProduct) ToCKANDataPackageJSON() ([]byte, error) {
	title := strings.TrimSpace(dp.Manifest.Title)
	out := CKANDataPackageJSON{
		Name:        Slugify(title),
		Title:       title,
		Description: dp.Description,
		Version:     dp.Manifest.Lineage.Version,
		Resources:   make([]FrictionlessResource, 0, len(dp.Resources)),
	}
	for _, r := range dp.Resources {
		out.Resources = append(out.Resources, FrictionlessResource{
			Name:     r.Name,
			Path:     r.Path,
			Format:   strings.ToLower(strings.TrimSpace(r.Format)),
			Bytes:    r.BytesCount,
			SHA256:   r.HashSHA256,
		})
	}

	out.Extras = map[string]interface{}{"dimensions": dp.Manifest.Dimensions}
	if dp.Manifest.Spatial != nil {
		out.Extras["spatial"] = dp.Manifest.Spatial
	}
	if dp.Manifest.Temporal != nil {
		out.Extras["temporal"] = dp.Manifest.Temporal
	}
	if dp.Manifest.Status != "" {
		out.Extras["status"] = dp.Manifest.Status
	}
	if emitter := dp.Manifest.Lineage.Emitter; emitter != nil {
		out.Extras["emitter"] = emitter.By
	} else if dp.Manifest.Emitter != nil {
		out.Extras["emitter"] = dp.Manifest.Emitter.By
	}
	if v := fmt.Sprintf("%v", dp.Manifest.Nature); v != "" {
		out.Extras["nature"] = v
	}

	return json.MarshalIndent(out, "", "  ")
}

// ToDCATJSON converts an ODKF DataProduct into a W3C DCAT-AP dataset JSON-LD document
// consumable by well-known catalogs of type "dcat" (ADR 0013).
func (dp *DataProduct) ToDCATJSON() ([]byte, error) {
	out := DCATDatasetJSON{
		Context:     DCATContext,
		Type:        "dcat:Dataset",
		ID:          dp.ID,
		Title:       dp.Manifest.Title,
		Description: dp.Description,
		Version:     dp.Manifest.Lineage.Version,
		Keywords:    dp.Manifest.Dimensions,
		Theme:       dp.Manifest.Dimensions,
	}
	if !dp.Manifest.Lineage.UpdatedAt.IsZero() {
		out.Modified = dp.Manifest.Lineage.UpdatedAt.Format(time.RFC3339)
	}
	if dp.Manifest.Lineage.Emitter != nil && !dp.Manifest.Lineage.Emitter.At.IsZero() {
		out.Issued = dp.Manifest.Lineage.Emitter.At.Format(time.RFC3339)
	}

	out.Distribution = make([]DCATDistribution, 0, len(dp.Resources))
	for _, r := range dp.Resources {
		out.Distribution = append(out.Distribution, DCATDistribution{
			Type:      "dcat:Distribution",
			Format:    strings.ToLower(strings.TrimSpace(r.Format)),
			AccessURL: r.Path,
			ByteSize:  r.BytesCount,
		})
	}
	return json.MarshalIndent(out, "", "  ")
}