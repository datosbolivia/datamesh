package usecases

import (
	"context"
	"fmt"
	"strings"
	"sync"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// DiscoverCatalogUseCase implements inbound.CatalogServicePort orchestrating federated catalog retrieval.
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

// DiscoverAll retrieves and aggregates all federated catalogs configured in Base.CatalogURLs.
func (uc *DiscoverCatalogUseCase) DiscoverAll(ctx context.Context) (*domain.Catalog, error) {
	urls := uc.config.Base.CatalogURLs
	if len(urls) == 0 {
		if uc.config.Base.CatalogURL != "" {
			urls = []string{uc.config.Base.CatalogURL}
		} else {
			urls = []string{"https://datosbolivia.github.io/llms.txt"}
		}
	}

	if len(urls) == 1 {
		return uc.resolver.FetchCatalog(ctx, urls[0])
	}

	type catResult struct {
		catalog *domain.Catalog
		err     error
		source  string
	}

	resultChan := make(chan catResult, len(urls))
	var wg sync.WaitGroup

	for _, u := range urls {
		wg.Add(1)
		go func(targetURL string) {
			defer wg.Done()
			cat, err := uc.resolver.FetchCatalog(ctx, targetURL)
			resultChan <- catResult{catalog: cat, err: err, source: targetURL}
		}(u)
	}

	wg.Wait()
	close(resultChan)

	combined := &domain.Catalog{
		Title:          "DataMesh Federated Catalog",
		Description:    "Aggregated decentralized sovereign data products",
		SourceURL:      "federated://all",
		SourceCatalogs: make([]string, 0, len(urls)),
		Entries:        make([]domain.CatalogEntry, 0),
	}

	var errorsList []string
	seenEntries := make(map[string]bool)

	for res := range resultChan {
		if res.err != nil {
			errorsList = append(errorsList, fmt.Sprintf("[%s]: %v", res.source, res.err))
			continue
		}
		combined.SourceCatalogs = append(combined.SourceCatalogs, res.source)
		for _, entry := range res.catalog.Entries {
			if entry.CatalogSource == "" {
				entry.CatalogSource = res.source
			}
			key := entry.ResolvedURL
			if key == "" {
				key = entry.Title
			}
			if !seenEntries[key] {
				seenEntries[key] = true
				combined.Entries = append(combined.Entries, entry)
			}
		}
	}

	if len(combined.Entries) == 0 && len(errorsList) > 0 {
		return nil, fmt.Errorf("failed to discover catalogs: %s", strings.Join(errorsList, "; "))
	}

	return combined, nil
}

// Discover loads and parses a target catalog or aggregates all configured catalogs if url is omitted.
func (uc *DiscoverCatalogUseCase) Discover(ctx context.Context, catalogURL string) (*domain.Catalog, error) {
	targetURL := strings.TrimSpace(catalogURL)
	if targetURL == "" {
		if len(uc.config.Base.CatalogURLs) > 1 {
			return uc.DiscoverAll(ctx)
		}
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
