package domain

import (
	"errors"
	"strings"
	"time"
)

var (
	ErrEmptyTitle       = errors.New("data product title cannot be empty")
	ErrInvalidType      = errors.New("data product type must be 'dataset', 'model', 'composite', 'component', or 'requirement'")
	ErrMissingDimension = errors.New("data product must specify at least one dimension")
)

// Contract defines a syntactic or semantic data contract adhering to OKF/ODKF v0.2.
// Supports both inline specification and by-reference resolution (ref).
type Contract struct {
	Type   string                 `json:"type" yaml:"type"`
	Path   string                 `json:"path,omitempty" yaml:"path,omitempty"`
	Ref    string                 `json:"ref,omitempty" yaml:"ref,omitempty"`       // By-Reference resolution (local path or remote URL)
	Inline map[string]interface{} `json:"inline,omitempty" yaml:"inline,omitempty"` // Inline contract specification
}

// EpistemicActor represents an epistemic agent or verifier in the provenance chain (emitter or attester).
type EpistemicActor struct {
	By        string                 `json:"by" yaml:"by"`                             // human:<id>, agent:<id>, process:<id>
	At        time.Time              `json:"at" yaml:"at"`                             // ISO 8601 timestamp
	Role      string                 `json:"role,omitempty" yaml:"role,omitempty"`     // raw-data-producer, validator, auditor
	Verdict   string                 `json:"verdict,omitempty" yaml:"verdict,omitempty"` // verified, refuted, pending
	TrustTier string                 `json:"trust_tier,omitempty" yaml:"trust_tier,omitempty"` // unverified, machine-confirmed, human-reviewed
	Signature *Signature             `json:"signature,omitempty" yaml:"signature,omitempty"`
	Metadata  map[string]interface{} `json:"metadata,omitempty" yaml:"metadata,omitempty"`
}

// Lineage tracks provenance, version, and timestamps according to PE3 and ODKF epistemic stack.
type Lineage struct {
	Sources         []string               `json:"sources" yaml:"sources"`
	Version         string                 `json:"version" yaml:"version"`
	UpdatedAt       time.Time              `json:"updated_at" yaml:"updated_at"`
	Emitter         *EpistemicActor        `json:"emitter,omitempty" yaml:"emitter,omitempty"`
	Attester        *EpistemicActor        `json:"attester,omitempty" yaml:"attester,omitempty"`
	Ref             string                 `json:"ref,omitempty" yaml:"ref,omitempty"` // By-Reference lineage external file
	Transformations []LineageTransformation `json:"transformations,omitempty" yaml:"transformations,omitempty"`
}

// Resource represents an individual tabular or binary asset within a Data Product.
type Resource struct {
	Name       string `json:"name" yaml:"name"`
	Path       string `json:"path" yaml:"path"`
	Format     string `json:"format" yaml:"format"`
	HashSHA256 string `json:"hash_sha256,omitempty" yaml:"hash_sha256,omitempty"`
	BytesCount int64  `json:"bytes_count,omitempty" yaml:"bytes_count,omitempty"`
}

// SpatialCoverage encapsulates geospatial extent and resolution per ISO 19115 / DCAT v3.
type SpatialCoverage struct {
	Country     string    `json:"country,omitempty" yaml:"country,omitempty"`
	Regions     []string  `json:"regions,omitempty" yaml:"regions,omitempty"`
	BBox        []float64 `json:"bbox,omitempty" yaml:"bbox,omitempty"` // [minX, minY, maxX, maxY]
	Granularity string    `json:"granularity,omitempty" yaml:"granularity,omitempty"`
}

// TemporalCoverage encapsulates temporal extent and frequency per ISO 8601 / DCAT.
type TemporalCoverage struct {
	Start     string `json:"start,omitempty" yaml:"start,omitempty"`
	End       string `json:"end,omitempty" yaml:"end,omitempty"`
	Frequency string `json:"frequency,omitempty" yaml:"frequency,omitempty"`
	Timezone  string `json:"timezone,omitempty" yaml:"timezone,omitempty"`
}

// QualityProfile encapsulates completeness and quality verification rules.
type QualityProfile struct {
	Status       string             `json:"status,omitempty" yaml:"status,omitempty"`
	Completeness float64            `json:"completeness,omitempty" yaml:"completeness,omitempty"`
	RowCount     int64              `json:"row_count,omitempty" yaml:"row_count,omitempty"`
	Checks       []QualityCheckRule `json:"checks,omitempty" yaml:"checks,omitempty"`
}

// QualityCheckRule defines a declarative assertion on data values.
type QualityCheckRule struct {
	Rule        string                 `json:"rule" yaml:"rule"`
	TargetField string                 `json:"field,omitempty" yaml:"field,omitempty"`
	Params      map[string]interface{} `json:"params,omitempty" yaml:"params,omitempty"`
}

// SemanticFieldMapping maps a raw tabular column to an ODKF concept document.
type SemanticFieldMapping struct {
	FieldName    string            `json:"field_name" yaml:"field_name"`
	ConceptRef   string            `json:"concept_ref,omitempty" yaml:"concept_ref,omitempty"`
	ValueMapping map[string]string `json:"value_mapping,omitempty" yaml:"value_mapping,omitempty"`
}

// PublicationTargetResult contains the execution status for a publication target.
type PublicationTargetResult struct {
	Target         string `json:"target"`
	Success        bool   `json:"success"`
	DestinationURI string `json:"destination_uri,omitempty"`
	Message        string `json:"message,omitempty"`
	Error          string `json:"error,omitempty"`
}

// Signature encapsulates cryptographic authorship proof (SSH / OpenPGP / Ed25519) per PE4 & ADR 0015.
type Signature struct {
	KeyID     string `json:"key_id" yaml:"key_id"`
	Algorithm string `json:"algorithm" yaml:"algorithm"`
	Signature string `json:"signature" yaml:"signature"`
	Verified  bool   `json:"verified" yaml:"verified"`
}

// Manifest represents the frontmatter header specified in OKF / ODKF v0.2.
type Manifest struct {
	Type       string            `json:"type" yaml:"type"`
	Title      string            `json:"title" yaml:"title"`
	Dimensions []string          `json:"dimensions" yaml:"dimensions"`
	Nature     string            `json:"nature,omitempty" yaml:"nature,omitempty"` // structured, semi-structured, unstructured
	Status     string            `json:"status,omitempty" yaml:"status,omitempty"` // draft, stable, verified, refuted, deprecated
	Supersedes string            `json:"supersedes,omitempty" yaml:"supersedes,omitempty"` // URI of superseded concept (Popperian falsability)
	Contracts  []Contract        `json:"contracts,omitempty" yaml:"contracts,omitempty"`
	Spatial    *SpatialCoverage  `json:"spatial,omitempty" yaml:"spatial,omitempty"`
	Temporal   *TemporalCoverage `json:"temporal,omitempty" yaml:"temporal,omitempty"`
	Quality    *QualityProfile   `json:"quality,omitempty" yaml:"quality,omitempty"`
	Lineage    Lineage           `json:"lineage" yaml:"lineage"`
	Emitter    *EpistemicActor   `json:"emitter,omitempty" yaml:"emitter,omitempty"`
	Attester   *EpistemicActor   `json:"attester,omitempty" yaml:"attester,omitempty"`
	Signatures []Signature       `json:"signatures,omitempty" yaml:"signatures,omitempty"`
}

// DataProduct is the Aggregate Root representing an Open Knowledge Format node.
type DataProduct struct {
	ID          string     `json:"id"`
	Manifest    Manifest   `json:"manifest"`
	Description string     `json:"description"`
	Resources   []Resource `json:"resources"`
	RawContent  string     `json:"raw_content,omitempty"`
}

// NewDataProduct instantiates and validates a DataProduct Aggregate Root.
func NewDataProduct(id string, manifest Manifest, description string, resources []Resource) (*DataProduct, error) {
	dp := &DataProduct{
		ID:          id,
		Manifest:    manifest,
		Description: description,
		Resources:   resources,
	}

	if err := dp.Validate(); err != nil {
		return nil, err
	}
	return dp, nil
}

// Validate checks domain invariants for OKF / ODKF v0.2 conformance.
func (dp *DataProduct) Validate() error {
	if strings.TrimSpace(dp.Manifest.Title) == "" {
		return ErrEmptyTitle
	}

	validType := false
	switch dp.Manifest.Type {
	case "dataset", "model", "composite", "component", "requirement", "document", "concept", "playbook", "metric", "indicator", "service", "catalog":
		validType = true
	}
	if !validType {
		return ErrInvalidType
	}

	return nil
}
