package usecases

import (
	"context"
	"fmt"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/inbound"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// HarvestCKANUseCase coordinates catalog discovery, authentication, CKAN ingestion, and OKF v0.2 reconstruction.
type HarvestCKANUseCase struct {
	wellKnownResolver outbound.WellKnownResolverPort
	ckanClient        outbound.CKANClientPort
	authProviders     map[string]outbound.AuthProviderPort
}

var _ inbound.HarvesterServicePort = (*HarvestCKANUseCase)(nil)

// NewHarvestCKANUseCase constructs an instance of HarvestCKANUseCase.
func NewHarvestCKANUseCase(
	wellKnownResolver outbound.WellKnownResolverPort,
	ckanClient outbound.CKANClientPort,
	authProviders map[string]outbound.AuthProviderPort,
) *HarvestCKANUseCase {
	if authProviders == nil {
		authProviders = make(map[string]outbound.AuthProviderPort)
	}
	return &HarvestCKANUseCase{
		wellKnownResolver: wellKnownResolver,
		ckanClient:        ckanClient,
		authProviders:     authProviders,
	}
}

// DiscoverWellKnown probes for /.well-known/datamesh.json to inspect required auth and catalog specs.
func (uc *HarvestCKANUseCase) DiscoverWellKnown(ctx context.Context, targetURL string) (*domain.WellKnownDiscovery, error) {
	if uc.wellKnownResolver == nil {
		return nil, fmt.Errorf("well-known resolver port is not configured")
	}
	return uc.wellKnownResolver.FetchWellKnown(ctx, targetURL)
}

// HarvestCKAN queries CKAN Action API and reconstructs OKF data packages.
func (uc *HarvestCKANUseCase) HarvestCKAN(ctx context.Context, ckanBaseURL string, options map[string]interface{}) (*domain.CKANHarvestResult, error) {
	start := time.Now()
	query := ""
	limit := 100
	offset := 0
	authType := "none"

	if q, ok := options["query"].(string); ok {
		query = q
	}
	if l, ok := options["limit"].(int); ok && l > 0 {
		limit = l
	}
	if o, ok := options["offset"].(int); ok && o >= 0 {
		offset = o
	}
	if at, ok := options["auth_type"].(string); ok {
		authType = at
	}

	auth := uc.authProviders[authType]

	packages, total, err := uc.ckanClient.SearchPackages(ctx, ckanBaseURL, query, offset, limit, auth)
	if err != nil {
		return nil, fmt.Errorf("failed to harvest packages from CKAN at %s: %w", ckanBaseURL, err)
	}

	var harvested []domain.PackageManifest
	for i := range packages {
		pkg := &packages[i]
		manifest, err := uc.ReconstructOKF(ctx, pkg)
		if err != nil {
			continue
		}
		harvested = append(harvested, *manifest)
	}

	return &domain.CKANHarvestResult{
		CatalogURL:        ckanBaseURL,
		TotalDiscovered:   total,
		HarvestedPackages: harvested,
		ExecutionTimeMs:   time.Since(start).Milliseconds(),
	}, nil
}

// ReconstructOKF transforms a raw CKANPackage into an OKF v0.2 PackageManifest,
// delegating the pure transformation to the domain layer (single source of truth).
func (uc *HarvestCKANUseCase) ReconstructOKF(ctx context.Context, pkg *domain.CKANPackage) (*domain.PackageManifest, error) {
	return domain.ReconstructManifestFromCKAN(pkg)
}
