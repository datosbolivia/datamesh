package usecases

import (
	"context"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// DiscoverCatalogUseCase implements inbound.CatalogServicePort orchestrating catalog retrieval.
type DiscoverCatalogUseCase struct {
	resolver outbound.CatalogResolverPort
	config   domain.Config
}

// NewDiscoverCatalogUseCase creates an initialized catalog use case.
func NewDiscoverCatalogUseCase(resolver outbound.CatalogResolverPort, cfg domain.Config) *DiscoverCatalogUseCase {
	return &DiscoverCatalogUseCase{
		resolver: resolver,
		config:   cfg,
	}
}

// Discover loads and parses the target catalog, falling back to base configuration.
func (uc *DiscoverCatalogUseCase) Discover(ctx context.Context, catalogURL string) (*domain.Catalog, error) {
	targetURL := strings.TrimSpace(catalogURL)
	if targetURL == "" {
		targetURL = uc.config.Base.CatalogURL
	}
	return uc.resolver.FetchCatalog(ctx, targetURL)
}

// Search retrieves the catalog and filters matching entries by keyword.
func (uc *DiscoverCatalogUseCase) Search(ctx context.Context, catalogURL, keyword string) ([]domain.CatalogEntry, error) {
	cat, err := uc.Discover(ctx, catalogURL)
	if err != nil {
		return nil, err
	}
	return cat.FindByKeyword(keyword), nil
}
