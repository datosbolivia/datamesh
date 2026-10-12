package usecases

import (
	"context"
	"encoding/json"
	"errors"
	"testing"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// fakeWellKnownResolver simulates a conformant /.well-known/datamesh.json endpoint.
type fakeWellKnownResolver struct {
	wk  *domain.WellKnownDiscovery
	err error
}

func (f *fakeWellKnownResolver) FetchWellKnown(ctx context.Context, targetURL string) (*domain.WellKnownDiscovery, error) {
	return f.wk, f.err
}

// fakeReader simulates the unified as-is manifest reader (llms.txt, datapackage.*, index.md).
type fakeReader struct {
	dp  *domain.DataProduct
	err error
}

func (f *fakeReader) RegisterParser(parser outbound.ManifestParserPort) {}
func (f *fakeReader) ReadPackage(ctx context.Context, uriOrPath string) (*domain.PackageManifest, error) {
	return nil, errors.New("not implemented in test fake")
}
func (f *fakeReader) ReadNode(ctx context.Context, uriOrPath string) (*domain.DataProduct, error) {
	return f.dp, f.err
}
func (f *fakeReader) ReadCatalog(ctx context.Context, uriOrPath string) (*domain.Catalog, error) {
	return nil, errors.New("not implemented in test fake")
}

// fakeCKANClient simulates the CKAN Action API for as-is ingestion.
type fakeCKANClient struct {
	pkg  *domain.CKANPackage
	err  error
	seen map[string]string
}

func (f *fakeCKANClient) SearchPackages(ctx context.Context, baseURL, query string, start, rows int, auth outbound.AuthProviderPort) ([]domain.CKANPackage, int, error) {
	return nil, 0, errors.New("not implemented in test fake")
}
func (f *fakeCKANClient) GetPackage(ctx context.Context, baseURL, packageID string, auth outbound.AuthProviderPort) (*domain.CKANPackage, error) {
	if f.seen != nil {
		f.seen["base"] = baseURL
		f.seen["id"] = packageID
	}
	return f.pkg, f.err
}
func (f *fakeCKANClient) GetDataStoreSchema(ctx context.Context, baseURL, resourceID string, auth outbound.AuthProviderPort) ([]domain.CKANDataStoreField, error) {
	return nil, errors.New("not implemented in test fake")
}

func dummyDataProduct() *domain.DataProduct {
	dp, _ := domain.NewDataProduct(
		"air_quality",
		domain.Manifest{
			Type:       "dataset",
			Title:      "Compilación de datos de calidad del aire de Bolivia",
			Dimensions: []string{"tema", "ubi_geo"},
		},
		"Dataset as-is sobre calidad del aire.",
		[]domain.Resource{{Name: "pm25", Path: "https://datos.bo/storage/air/pm25.csv", Format: "csv", BytesCount: 1200}},
	)
	return dp
}

func TestAsIsIngestUseCase_ConformantOKF(t *testing.T) {
	dp := dummyDataProduct()
	uc := NewAsIsIngestUseCase(
		&fakeWellKnownResolver{wk: &domain.WellKnownDiscovery{Catalog: domain.CatalogMetadata{Type: "okf"}}},
		&fakeReader{dp: dp},
		nil, nil,
	)
	got, err := uc.Ingest(context.Background(), "https://datos.bo", "none")
	if err != nil {
		t.Fatalf("Ingest error: %v", err)
	}
	if got.ID != "air_quality" {
		t.Fatalf("expected ID air_quality, got %q", got.ID)
	}
}

func TestAsIsIngestUseCase_FallbackToRawReader(t *testing.T) {
	// No well-known endpoint: the probe chain must still read the source as-is.
	dp := dummyDataProduct()
	uc := NewAsIsIngestUseCase(
		&fakeWellKnownResolver{wk: nil, err: errors.New("404")},
		&fakeReader{dp: dp},
		nil, nil,
	)
	got, err := uc.Ingest(context.Background(), "https://datos.bo/nodo/index.md", "")
	if err != nil {
		t.Fatalf("Ingest error: %v", err)
	}
	if got.ID != "air_quality" {
		t.Fatalf("expected ID air_quality, got %q", got.ID)
	}
}

func TestAsIsIngestUseCase_RawCKANReconstruction(t *testing.T) {
	client := &fakeCKANClient{
		pkg: &domain.CKANPackage{
			ID:      "abc-123",
			Name:    "calidad-aire",
			Title:   "Calidad del aire de Bolivia",
			Notes:   "Resumen del dataset.",
			Version: "1.2.0",
			Resources: []domain.CKANResource{
				{ID: "res-1", Name: "pm25.csv", URL: "https://datos.bo/storage/pm25.csv", Format: "CSV", Size: 999},
			},
			Tags: []domain.CKANTag{{Name: "aire"}},
		},
		seen: map[string]string{},
	}
	uc := NewAsIsIngestUseCase(
		&fakeWellKnownResolver{wk: &domain.WellKnownDiscovery{Catalog: domain.CatalogMetadata{
			Type:        "ckan",
			APIEndpoint: "https://datos.bo/api/3/action",
		}}},
		nil, client, nil,
	)

	got, err := uc.Ingest(context.Background(), "https://datos.bo/dataset/calidad-aire", "none")
	if err != nil {
		t.Fatalf("Ingest error: %v", err)
	}
	if got.ID != "calidad_aire" {
		t.Fatalf("expected reporter ID calidad_aire, got %q", got.ID)
	}
	if len(got.Resources) != 1 || got.Resources[0].Format != "csv" {
		t.Fatalf("resources not normalized to ODKF: %+v", got.Resources)
	}
	if client.seen["id"] != "calidad-aire" {
		t.Fatalf("package id extracted incorrectly: %v", client.seen)
	}
}

func TestAsIsIngestUseCase_CKANCatalogRootRejected(t *testing.T) {
	client := &fakeCKANClient{err: errors.New("should not be called")}
	uc := NewAsIsIngestUseCase(nil, nil, client, nil)

	if _, err := uc.Ingest(context.Background(), "https://datos.bo/api/3/action/package_search", ""); err == nil {
		t.Fatal("expected error when target selects the catalog root, not a dataset")
	}
}

func TestAsIsIngestUseCase_ExportCKAN(t *testing.T) {
	uc := NewAsIsIngestUseCase(nil, nil, nil, nil)
	raw, err := uc.ExportCKANDataPackage(context.Background(), dummyDataProduct())
	if err != nil {
		t.Fatalf("ExportCKANDataPackage error: %v", err)
	}
	var out domain.CKANDataPackageJSON
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatalf("invalid CKAN datapackage JSON: %v", err)
	}
	if out.Name != "compilaci_n_de_datos_de_calidad_del_aire_de_bolivia" {
		t.Fatalf("unexpected datapackage name: %q", out.Name)
	}
	if len(out.Resources) != 1 || out.Resources[0].Format != "csv" {
		t.Fatalf("resources not exported: %+v", out.Resources)
	}
	if _, ok := out.Extras["dimensions"]; !ok {
		t.Fatalf("ODKF dimensions missing from extras: %+v", out.Extras)
	}
}

func TestAsIsIngestUseCase_ExportDCAT(t *testing.T) {
	uc := NewAsIsIngestUseCase(nil, nil, nil, nil)
	raw, err := uc.ExportDCAT(context.Background(), dummyDataProduct())
	if err != nil {
		t.Fatalf("ExportDCAT error: %v", err)
	}
	var out domain.DCATDatasetJSON
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatalf("invalid DCAT JSON: %v", err)
	}
	if out.Type != "dcat:Dataset" {
		t.Fatalf("expected dcat:Dataset, got %q", out.Type)
	}
	if len(out.Distribution) != 1 || out.Distribution[0].AccessURL == "" {
		t.Fatalf("distribution not exported: %+v", out.Distribution)
	}
}

func TestDataProductFromManifest_DimensionsFromMetadata(t *testing.T) {
	pm := &domain.PackageManifest{
		Name:        "censo-2024",
		Title:       "Censo Nacional 2024",
		Description: "Resultados del censo.",
		Metadata: map[string]interface{}{
			"dimensions": []interface{}{"tema", "ubi_geo"},
			"type":       "dataset",
		},
	}
	dp, err := dataProductFromManifest(pm)
	if err != nil {
		t.Fatalf("dataProductFromManifest error: %v", err)
	}
	if len(dp.Manifest.Dimensions) != 2 || dp.Manifest.Dimensions[0] != "tema" {
		t.Fatalf("dimensions not lifted to ODKF: %+v", dp.Manifest.Dimensions)
	}
	if dp.Manifest.Type != "dataset" {
		t.Fatalf("type not lifted: %+v", dp.Manifest.Type)
	}
}
