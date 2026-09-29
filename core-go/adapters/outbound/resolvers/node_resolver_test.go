package resolvers

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestNodeDataProductResolver(t *testing.T) {
	nodeMarkdown := `---
type: dataset
title: Atlas Electoral y Elecciones Generales de Bolivia (1979-2025)
dimensions:
- año
- departamento
- circunscripcion
- partido
contracts:
- type: datapackage
  path: ./datapackage.yaml
lineage:
  version: 1.0.0
---

# Atlas Electoral

Descripción detallada del dataset de elecciones.
`
	tmpDir := t.TempDir()
	filePath := filepath.Join(tmpDir, "index.md")
	if err := os.WriteFile(filePath, []byte(nodeMarkdown), 0644); err != nil {
		t.Fatal(err)
	}

	resolver := NewNodeDataProductResolver(5 * time.Second)
	dp, err := resolver.FetchDataProduct(context.Background(), "file://"+filePath)
	if err != nil {
		t.Fatalf("unexpected error resolving node: %v", err)
	}

	if dp.Manifest.Title != "Atlas Electoral y Elecciones Generales de Bolivia (1979-2025)" {
		t.Errorf("title mismatch: %s", dp.Manifest.Title)
	}
	if dp.Manifest.Type != "dataset" {
		t.Errorf("type mismatch: %s", dp.Manifest.Type)
	}
	if len(dp.Manifest.Dimensions) != 4 {
		t.Errorf("expected 4 dimensions, got %d", len(dp.Manifest.Dimensions))
	}
	if len(dp.Manifest.Contracts) != 1 || dp.Manifest.Contracts[0].Type != "datapackage" {
		t.Errorf("contracts mismatch: %v", dp.Manifest.Contracts)
	}
	if dp.Manifest.Lineage.Version != "1.0.0" {
		t.Errorf("version mismatch: %s", dp.Manifest.Lineage.Version)
	}
}
