package outbound

import (
	"context"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// CatalogResolverPort abstracts reading and parsing llms.txt or federated catalog endpoints.
type CatalogResolverPort interface {
	FetchCatalog(ctx context.Context, url string) (*domain.Catalog, error)
}

// DataProductResolverPort abstracts fetching remote OKF node files and extracting manifests.
type DataProductResolverPort interface {
	FetchDataProduct(ctx context.Context, resolvedURL string) (*domain.DataProduct, error)
}
