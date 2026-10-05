package domain

import "time"

// CKANResource represents a downloadable asset or API endpoint in a CKAN dataset.
type CKANResource struct {
	ID              string                 `json:"id"`
	Name            string                 `json:"name"`
	Description     string                 `json:"description,omitempty"`
	URL             string                 `json:"url"`
	Format          string                 `json:"format"`
	MimeType        string                 `json:"mimetype,omitempty"`
	Size            int64                  `json:"size,omitempty"`
	DatastoreActive bool                   `json:"datastore_active,omitempty"`
	Fields          []CKANDataStoreField   `json:"fields,omitempty"`
}

// CKANDataStoreField represents a schema field from the CKAN DataStore extension.
type CKANDataStoreField struct {
	ID   string `json:"id"`
	Type string `json:"type"` // "text", "numeric", "timestamp", "int4", etc.
}

// CKANExtra represents key-value metadata in CKAN.
type CKANExtra struct {
	Key   string      `json:"key"`
	Value interface{} `json:"value"`
}

// CKANPackage represents a complete dataset object retrieved from CKAN Action API v3.
type CKANPackage struct {
	ID               string                 `json:"id"`
	Name             string                 `json:"name"`
	Title            string                 `json:"title"`
	Notes            string                 `json:"notes,omitempty"`
	URL              string                 `json:"url,omitempty"`
	Version          string                 `json:"version,omitempty"`
	Author           string                 `json:"author,omitempty"`
	Maintainer       string                 `json:"maintainer,omitempty"`
	LicenseTitle     string                 `json:"license_title,omitempty"`
	MetadataCreated  *time.Time             `json:"metadata_created,omitempty"`
	MetadataModified *time.Time             `json:"metadata_modified,omitempty"`
	Organization     *CKANOrganization      `json:"organization,omitempty"`
	Groups           []CKANGroup            `json:"groups,omitempty"`
	Tags             []CKANTag              `json:"tags,omitempty"`
	Extras           []CKANExtra            `json:"extras,omitempty"`
	Resources        []CKANResource         `json:"resources"`
	CustomMetadata   map[string]interface{} `json:"custom_metadata,omitempty"`
}

// CKANOrganization represents the publisher entity in CKAN.
type CKANOrganization struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Title       string `json:"title"`
	Description string `json:"description,omitempty"`
}

// CKANGroup represents a thematic category in CKAN.
type CKANGroup struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Title string `json:"title"`
}

// CKANTag represents a keyword tag in CKAN.
type CKANTag struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

// CKANHarvestResult contains the execution summary and reconstructed OKF artifacts.
type CKANHarvestResult struct {
	CatalogURL       string             `json:"catalog_url"`
	TotalDiscovered  int                `json:"total_discovered"`
	HarvestedPackages []PackageManifest `json:"harvested_packages"`
	OutputDirectory  string             `json:"output_directory,omitempty"`
	ExecutionTimeMs  int64              `json:"execution_time_ms"`
}
