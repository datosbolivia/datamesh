package usecases

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
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

// ReconstructOKF transforms a raw CKANPackage into an OKF v0.2 PackageManifest.
func (uc *HarvestCKANUseCase) ReconstructOKF(ctx context.Context, pkg *domain.CKANPackage) (*domain.PackageManifest, error) {
	if pkg == nil {
		return nil, fmt.Errorf("cannot reconstruct nil CKAN package")
	}

	manifestName := domain.Slugify(pkg.Name)
	if manifestName == "" {
		manifestName = domain.Slugify(pkg.Title)
	}

	var resources []domain.Resource
	for _, r := range pkg.Resources {
		resFormat := strings.ToLower(strings.TrimSpace(r.Format))
		if resFormat == "" {
			resFormat = "csv"
		}
		resName := domain.Slugify(r.Name)
		if resName == "" {
			resName = fmt.Sprintf("resource_%s", r.ID[:8])
		}

		resources = append(resources, domain.Resource{
			Name:       resName,
			Path:       r.URL,
			Format:     resFormat,
			BytesCount: r.Size,
		})
	}

	// Extract extras: spatial, temporal, quality
	metadata := make(map[string]interface{})
	var spatialCoverage *domain.SpatialCoverage
	var temporalCoverage *domain.TemporalCoverage

	for _, extra := range pkg.Extras {
		key := strings.ToLower(strings.TrimSpace(extra.Key))
		valStr := fmt.Sprintf("%v", extra.Value)

		switch key {
		case "spatial", "spatial-coverage", "spatial_coverage":
			spatialCoverage = parseSpatialExtra(valStr)
		case "temporal_start", "temporal_start_date":
			if temporalCoverage == nil {
				temporalCoverage = &domain.TemporalCoverage{}
			}
			temporalCoverage.Start = valStr
		case "temporal_end", "temporal_end_date":
			if temporalCoverage == nil {
				temporalCoverage = &domain.TemporalCoverage{}
			}
			temporalCoverage.End = valStr
		case "frequency", "accrualperiodicity":
			if temporalCoverage == nil {
				temporalCoverage = &domain.TemporalCoverage{}
			}
			temporalCoverage.Frequency = valStr
		default:
			metadata[extra.Key] = extra.Value
		}
	}

	if spatialCoverage != nil {
		metadata["spatial"] = spatialCoverage
	}
	if temporalCoverage != nil {
		metadata["temporal"] = temporalCoverage
	}

	var tags []string
	for _, t := range pkg.Tags {
		tags = append(tags, t.Name)
	}
	metadata["tags"] = tags

	if pkg.Organization != nil {
		metadata["publisher"] = pkg.Organization.Title
	}

	return &domain.PackageManifest{
		Name:        manifestName,
		Title:       pkg.Title,
		Description: pkg.Notes,
		Format:      domain.PackageFormatDataPackageYAML,
		Version:     pkg.Version,
		Resources:   resources,
		Metadata:    metadata,
	}, nil
}

func parseSpatialExtra(val string) *domain.SpatialCoverage {
	val = strings.TrimSpace(val)
	if strings.HasPrefix(val, "{") {
		// GeoJSON BBox or geometry
		var geojson map[string]interface{}
		if err := json.Unmarshal([]byte(val), &geojson); err == nil {
			if bboxRaw, ok := geojson["bbox"].([]interface{}); ok && len(bboxRaw) == 4 {
				bbox := make([]float64, 4)
				for i := 0; i < 4; i++ {
					if f, ok := bboxRaw[i].(float64); ok {
						bbox[i] = f
					}
				}
				return &domain.SpatialCoverage{
					BBox:        bbox,
					Granularity: "geojson",
				}
			}
		}
	} else if strings.Contains(val, ",") {
		parts := strings.Split(val, ",")
		if len(parts) == 4 {
			bbox := make([]float64, 4)
			valid := true
			for i, p := range parts {
				f, err := strconv.ParseFloat(strings.TrimSpace(p), 64)
				if err != nil {
					valid = false
					break
				}
				bbox[i] = f
			}
			if valid {
				return &domain.SpatialCoverage{
					BBox:        bbox,
					Granularity: "bounding_box",
				}
			}
		}
	}
	return &domain.SpatialCoverage{
		Country: val,
	}
}
