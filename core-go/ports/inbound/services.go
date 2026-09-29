package inbound

import (
	"context"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// CatalogServicePort defines inbound operations for discovering and querying sovereign data catalogs.
type CatalogServicePort interface {
	Discover(ctx context.Context, catalogURL string) (*domain.Catalog, error)
	Search(ctx context.Context, catalogURL, keyword string) ([]domain.CatalogEntry, error)
}

// DataProductServicePort defines inbound operations for resolving and validating Data Products.
type DataProductServicePort interface {
	Resolve(ctx context.Context, uriOrURL string) (*domain.DataProduct, error)
	Validate(ctx context.Context, dp *domain.DataProduct) error
}

// ConfigServicePort defines inbound operations for obtaining active configuration settings.
type ConfigServicePort interface {
	GetConfig() domain.Config
}
