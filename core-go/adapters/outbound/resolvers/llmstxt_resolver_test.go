package resolvers

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestLLMSTxtParser(t *testing.T) {
	rawContent := `# Datos Bolivia
> Portal catálogo de Datos Abiertos de Bolivia

Este archivo expone el catálogo federado de datos abiertos.

## Catálogo de Datasets Federados (Open Knowledge Format v0.2)
- [Atlas Electoral y Elecciones Generales de Bolivia (1979-2025)](/raw/nodes/elecciones-bolivia/index.md): Conjunto de datos estructurados sobre la historia democrática. (Dominio: Demografía, Censos y Sociedad. Recursos: elecciones_generales_2020)
- [Cartera de Créditos del Sistema Financiero Boliviano (ASFI)](/raw/nodes/cartera-creditos/index.md): Datos estructurados sobre colocación de créditos. (Dominio: Economía, Moneda y Finanzas. Recursos: creditos)
`
	tmpDir := t.TempDir()
	filePath := filepath.Join(tmpDir, "llms.txt")
	if err := os.WriteFile(filePath, []byte(rawContent), 0644); err != nil {
		t.Fatal(err)
	}

	resolver := NewLLMSTxtCatalogResolver(5 * time.Second)
	fileURL := "file://" + filePath
	cat, err := resolver.FetchCatalog(context.Background(), fileURL)
	if err != nil {
		t.Fatalf("unexpected error parsing catalog: %v", err)
	}

	if cat.Title != "Datos Bolivia" {
		t.Errorf("expected title 'Datos Bolivia', got %s", cat.Title)
	}
	if len(cat.Entries) != 2 {
		t.Fatalf("expected 2 entries, got %d", len(cat.Entries))
	}

	e1 := cat.Entries[0]
	if e1.Title != "Atlas Electoral y Elecciones Generales de Bolivia (1979-2025)" {
		t.Errorf("entry 1 title mismatch: %s", e1.Title)
	}
	if e1.Domain != "Demografía, Censos y Sociedad" {
		t.Errorf("entry 1 domain mismatch: %s", e1.Domain)
	}
	if len(e1.Resources) != 1 || e1.Resources[0] != "elecciones_generales_2020" {
		t.Errorf("entry 1 resources mismatch: %v", e1.Resources)
	}

	// Test Search
	matches := cat.FindByKeyword("Créditos")
	if len(matches) != 1 {
		t.Errorf("expected 1 match for 'Créditos', got %d", len(matches))
	}
}
