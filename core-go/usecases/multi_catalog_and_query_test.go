package usecases

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/engine"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/resolvers"
	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

func TestMultiCatalogDiscovery(t *testing.T) {
	cat1Path, _ := filepath.Abs("../testdata/mock_catalog_primary.txt")
	cat2Path, _ := filepath.Abs("../testdata/mock_catalog_secondary.txt")

	cfg := domain.NewDefaultConfig()
	cfg.Base.CatalogURLs = []string{"file://" + cat1Path, "file://" + cat2Path}

	resolver := resolvers.NewLLMSTxtCatalogResolver(5 * time.Second)
	uc := NewDiscoverCatalogUseCase(resolver, cfg)

	cat, err := uc.DiscoverAll(context.Background())
	if err != nil {
		t.Fatalf("unexpected error discovering multiple catalogs: %v", err)
	}

	if len(cat.Entries) != 4 {
		t.Fatalf("expected 4 aggregated entries across 2 catalogs, got %d", len(cat.Entries))
	}
	if len(cat.SourceCatalogs) != 2 {
		t.Errorf("expected 2 source catalogs, got %d", len(cat.SourceCatalogs))
	}

	// Verify entries have CatalogSource set
	for _, entry := range cat.Entries {
		if entry.CatalogSource == "" {
			t.Errorf("entry %s missing CatalogSource", entry.Title)
		}
	}

	// Test cross-catalog keyword search
	results, err := uc.Search(context.Background(), "", "presupuesto")
	if err != nil {
		t.Fatalf("search failed: %v", err)
	}
	if len(results) != 1 || results[0].Title != "Presupuesto Municipal 2024" {
		t.Errorf("unexpected search results: %v", results)
	}
}

func TestQueryEngineExecution(t *testing.T) {
	csvPath, _ := filepath.Abs("../testdata/mock_data_elecciones.csv")

	queryEngine := engine.NewInMemTabularQueryEngine()
	queryUC := NewQueryDataProductUseCase(queryEngine, nil, nil)

	// Test SQL Triad Extraction
	sqlSample := `SELECT departamento, SUM(votos_validos) FROM "bolivia:elecciones:votos_2020" JOIN 'municipal:presupuesto:gastos' GROUP BY departamento`
	triads := domain.ExtractTriadsFromSQL(sqlSample)
	if len(triads) != 2 {
		t.Fatalf("expected 2 extracted triads, got %d", len(triads))
	}
	if triads[0].String() != "bolivia:elecciones:votos_2020" {
		t.Errorf("triad 0 mismatch: %s", triads[0].String())
	}
	if triads[1].String() != "municipal:presupuesto:gastos" {
		t.Errorf("triad 1 mismatch: %s", triads[1].String())
	}

	// Query with filter
	req := domain.QueryRequest{
		ResourceURI: "file://" + csvPath,
		Filters: map[string]string{
			"departamento": "La Paz",
		},
	}

	res, err := queryUC.Query(context.Background(), req)
	if err != nil {
		t.Fatalf("query execution failed: %v", err)
	}

	if res.RowCount != 2 {
		t.Fatalf("expected 2 rows for La Paz, got %d", res.RowCount)
	}

	if len(res.Columns) != 5 {
		t.Errorf("expected 5 columns, got %d", len(res.Columns))
	}

	// Test query with limit
	reqLimit := domain.QueryRequest{
		ResourceURI: "file://" + csvPath,
		Limit:       1,
	}
	resLimit, err := queryUC.Query(context.Background(), reqLimit)
	if err != nil {
		t.Fatalf("query with limit failed: %v", err)
	}
	if resLimit.RowCount != 1 {
		t.Errorf("expected 1 row with limit=1, got %d", resLimit.RowCount)
	}
}
