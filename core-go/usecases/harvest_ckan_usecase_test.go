package usecases

import (
	"context"
	"testing"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

type mockWellKnownResolver struct {
	discovery *domain.WellKnownDiscovery
}

func (m *mockWellKnownResolver) FetchWellKnown(ctx context.Context, targetURL string) (*domain.WellKnownDiscovery, error) {
	return m.discovery, nil
}

type mockCKANClient struct {
	packages []domain.CKANPackage
}

func (m *mockCKANClient) SearchPackages(ctx context.Context, baseURL string, query string, start, rows int, auth outbound.AuthProviderPort) ([]domain.CKANPackage, int, error) {
	return m.packages, len(m.packages), nil
}

func (m *mockCKANClient) GetPackage(ctx context.Context, baseURL, packageID string, auth outbound.AuthProviderPort) (*domain.CKANPackage, error) {
	if len(m.packages) > 0 {
		return &m.packages[0], nil
	}
	return nil, nil
}

func (m *mockCKANClient) GetDataStoreSchema(ctx context.Context, baseURL, resourceID string, auth outbound.AuthProviderPort) ([]domain.CKANDataStoreField, error) {
	return []domain.CKANDataStoreField{
		{ID: "id", Type: "int4"},
		{ID: "departamento", Type: "text"},
		{ID: "total", Type: "numeric"},
	}, nil
}

func TestHarvestCKANUseCase_ReconstructOKF(t *testing.T) {
	mockClient := &mockCKANClient{
		packages: []domain.CKANPackage{
			{
				ID:    "pkg-01",
				Name:  "censo-poblacion-2024",
				Title: "Censo de Población y Vivienda 2024",
				Notes: "Microdatos censales de Bolivia",
				Resources: []domain.CKANResource{
					{
						ID:     "res-01",
						Name:   "Población Departamental",
						URL:    "https://datos.gob.bo/dataset/censo.csv",
						Format: "CSV",
						Size:   1048576,
					},
				},
				Extras: []domain.CKANExtra{
					{Key: "spatial", Value: "-69.64,-22.90,-57.45,-9.67"},
					{Key: "temporal_start", Value: "2024-03-23"},
					{Key: "temporal_end", Value: "2024-03-25"},
				},
				Tags: []domain.CKANTag{
					{Name: "demografia"},
					{Name: "censo"},
				},
			},
		},
	}

	mockResolver := &mockWellKnownResolver{
		discovery: &domain.WellKnownDiscovery{
			SchemaVersion: "0.2.0",
			Catalog: domain.CatalogMetadata{
				Name:        "datos-gob-bo",
				Title:       "Portal de Datos Abiertos",
				Type:        "ckan",
				CatalogURL:  "https://datos.gob.bo",
				APIEndpoint: "https://datos.gob.bo/api/3/action",
			},
			Auth: domain.AuthConfiguration{
				Type:     "keycloak",
				Required: false,
			},
		},
	}

	uc := NewHarvestCKANUseCase(mockResolver, mockClient, nil)

	// Test 1: Discover well-known
	disc, err := uc.DiscoverWellKnown(context.Background(), "https://datos.gob.bo")
	if err != nil {
		t.Fatalf("unexpected discovery error: %v", err)
	}
	if disc.Catalog.Type != "ckan" {
		t.Errorf("expected catalog type ckan, got %s", disc.Catalog.Type)
	}

	// Test 2: Harvest and reconstruct
	res, err := uc.HarvestCKAN(context.Background(), "https://datos.gob.bo", map[string]interface{}{"limit": 10})
	if err != nil {
		t.Fatalf("unexpected harvest error: %v", err)
	}
	if res.TotalDiscovered != 1 {
		t.Errorf("expected 1 discovered package, got %d", res.TotalDiscovered)
	}

	pkgManifest := res.HarvestedPackages[0]
	if pkgManifest.Name != "censo_poblacion_2024" {
		t.Errorf("expected slug censo_poblacion_2024, got %s", pkgManifest.Name)
	}
	if len(pkgManifest.Resources) != 1 {
		t.Fatalf("expected 1 resource, got %d", len(pkgManifest.Resources))
	}
	if pkgManifest.Resources[0].Format != "csv" {
		t.Errorf("expected format csv, got %s", pkgManifest.Resources[0].Format)
	}

	spatial, ok := pkgManifest.Metadata["spatial"].(*domain.SpatialCoverage)
	if !ok || len(spatial.BBox) != 4 {
		t.Errorf("expected spatial bbox with 4 bounds, got %v", spatial)
	}
}
