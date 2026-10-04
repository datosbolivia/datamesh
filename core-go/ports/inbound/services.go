package inbound

import (
	"context"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// CatalogServicePort defines inbound operations for discovering and querying sovereign data catalogs.
type CatalogServicePort interface {
	DiscoverAll(ctx context.Context) (*domain.Catalog, error)
	Discover(ctx context.Context, catalogURL string) (*domain.Catalog, error)
	Search(ctx context.Context, catalogURL, keyword string) ([]domain.CatalogEntry, error)
}

// DataProductServicePort defines inbound operations for resolving and validating Data Products.
type DataProductServicePort interface {
	Resolve(ctx context.Context, uriOrURL string) (*domain.DataProduct, error)
	Validate(ctx context.Context, dp *domain.DataProduct) error
}

// QueryServicePort defines inbound operations for executing queries against data resources.
type QueryServicePort interface {
	Query(ctx context.Context, req domain.QueryRequest) (*domain.QueryResult, error)
	ExecuteSQL(ctx context.Context, sqlQuery string) (*domain.QueryResult, error)
}

// ConfigServicePort defines inbound operations for obtaining active configuration settings.
type ConfigServicePort interface {
	GetConfig() domain.Config
}

// PublicationServicePort defines inbound operations for publishing datasets and ODKF bundles across platforms.
type PublicationServicePort interface {
	Publish(ctx context.Context, datasetPath string, targets []string, options map[string]interface{}) ([]domain.PublicationTargetResult, error)
}

// SemanticServicePort defines inbound operations for semantic concept alignment and mapping.
type SemanticServicePort interface {
	AlignSemantics(ctx context.Context, manifest *domain.PackageManifest) ([]domain.SemanticFieldMapping, error)
	GenerateCaseExpression(ctx context.Context, mapping domain.SemanticFieldMapping, tablePrefix string) string
}
