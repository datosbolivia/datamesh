package manifests

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

func TestDataPackageJSONParser(t *testing.T) {
	jsonContent := `{
		"name": "estadisticas-agetic",
		"title": "Estadísticas AGETIC",
		"resources": [
			{
				"name": "Estadisticas Ciudadania Digital",
				"path": "data/ciudadania.csv",
				"format": "csv",
				"bytes": 1024
			},
			{
				"name": "interoperabilidad",
				"path": "https://remote.com/data.parquet"
			}
		]
	}`

	parser := NewDataPackageJSONParser()
	if !parser.CanParse("datapackage.json", []byte(jsonContent)) {
		t.Fatal("expected parser to handle datapackage.json")
	}

	manifest, err := parser.ParseManifest(context.Background(), []byte(jsonContent), "https://example.com/nodes/agetic/datapackage.json")
	if err != nil {
		t.Fatalf("failed to parse json manifest: %v", err)
	}

	if manifest.Name != "estadisticas-agetic" {
		t.Errorf("name mismatch: %s", manifest.Name)
	}
	if len(manifest.Resources) != 2 {
		t.Fatalf("expected 2 resources, got %d", len(manifest.Resources))
	}

	res0 := manifest.Resources[0]
	if res0.Name != "Estadisticas Ciudadania Digital" || res0.Format != "csv" || res0.BytesCount != 1024 {
		t.Errorf("res0 mismatch: %+v", res0)
	}
	if res0.Path != "https://example.com/nodes/agetic/data/ciudadania.csv" {
		t.Errorf("res0 path resolution mismatch: %s", res0.Path)
	}

	res1 := manifest.Resources[1]
	if res1.Format != "parquet" {
		t.Errorf("expected format inferred as parquet, got: %s", res1.Format)
	}
	if res1.Path != "https://remote.com/data.parquet" {
		t.Errorf("res1 path mismatch: %s", res1.Path)
	}
}

func TestDataPackageYAMLParser(t *testing.T) {
	yamlContent := `name: p2p-bob-exchange
title: Mercado Cambiario P2P BOB / USDT
resources:
- name: advertiser
  path: https://www.kaggle.com/datasets/andreschirinos/p2p-bob-exchange/advertiser.parquet
  format: parquet
  bytes_count: 2048
- name: Compilación de datos de calidad del aire de Bolivia
  path: data/calidad_aire.csv
`

	parser := NewDataPackageYAMLParser()
	if !parser.CanParse("datapackage.yaml", []byte(yamlContent)) {
		t.Fatal("expected parser to handle datapackage.yaml")
	}
	if !parser.CanParse("datapackage.yml", []byte(yamlContent)) {
		t.Fatal("expected parser to handle datapackage.yml")
	}

	manifest, err := parser.ParseManifest(context.Background(), []byte(yamlContent), "/local/nodes/p2p/datapackage.yaml")
	if err != nil {
		t.Fatalf("failed to parse yaml manifest: %v", err)
	}

	if manifest.Name != "p2p-bob-exchange" {
		t.Errorf("name mismatch: %s", manifest.Name)
	}
	if len(manifest.Resources) != 2 {
		t.Fatalf("expected 2 resources, got %d", len(manifest.Resources))
	}

	r0, found := manifest.FindResource("advertiser")
	if !found || r0.Format != "parquet" || r0.BytesCount != 2048 {
		t.Errorf("r0 find mismatch: %+v", r0)
	}

	r1, found := manifest.FindResource("compilacion_de_datos_de_calidad_del_aire_de_bolivia")
	if !found || r1.Format != "csv" {
		t.Errorf("r1 find by slug mismatch: %+v", r1)
	}
}

func TestOKFMarkdownParser(t *testing.T) {
	mdContent := `---
type: dataset
title: Censo Nacional de Poblacion y Vivienda
dimensions:
- departamento
- provincia
contracts:
- type: datapackage
  path: ./datapackage.json
lineage:
  version: 2.1.0
---

# Documentacion Censo

Detalles sobre el censo de Bolivia.
`

	parser := NewOKFMarkdownParser()
	if !parser.CanParse("index.md", []byte(mdContent)) {
		t.Fatal("expected parser to handle index.md")
	}

	manifest, err := parser.ParseManifest(context.Background(), []byte(mdContent), "")
	if err != nil {
		t.Fatalf("failed to parse markdown manifest: %v", err)
	}

	if manifest.Title != "Censo Nacional de Poblacion y Vivienda" {
		t.Errorf("title mismatch: %s", manifest.Title)
	}
	if manifest.Version != "2.1.0" {
		t.Errorf("version mismatch: %s", manifest.Version)
	}
}

func TestUnifiedMetadataReader(t *testing.T) {
	tmpDir := t.TempDir()
	nodeDir := filepath.Join(tmpDir, "air_quality")
	if err := os.MkdirAll(nodeDir, 0755); err != nil {
		t.Fatal(err)
	}

	indexContent := `---
type: dataset
title: Calidad del Aire
dimensions:
- fecha
- lugar
---
# Calidad del Aire en Bolivia
`
	if err := os.WriteFile(filepath.Join(nodeDir, "index.md"), []byte(indexContent), 0644); err != nil {
		t.Fatal(err)
	}

	pkgYaml := `name: air_quality
resources:
- name: mediciones
  path: https://remote.io/mediciones.csv
  format: csv
`
	if err := os.WriteFile(filepath.Join(nodeDir, "datapackage.yaml"), []byte(pkgYaml), 0644); err != nil {
		t.Fatal(err)
	}

	reader := NewUnifiedMetadataReader("", 5*time.Second)

	// Test ReadNode
	dp, err := reader.ReadNode(context.Background(), nodeDir)
	if err != nil {
		t.Fatalf("failed to read node: %v", err)
	}

	if dp.Manifest.Title != "Calidad del Aire" {
		t.Errorf("title mismatch: %s", dp.Manifest.Title)
	}
	if len(dp.Resources) != 1 || dp.Resources[0].Name != "mediciones" {
		t.Errorf("resources mismatch: %+v", dp.Resources)
	}

	// Test ResolveTriad
	triad := domain.ResourceTriad{
		Dataset:  "air_quality",
		Resource: "mediciones",
	}

	resolved, err := reader.ResolveTriad(context.Background(), triad)
	if err != nil {
		t.Fatalf("failed to resolve triad: %v", err)
	}
	if resolved.Triad.Dataset != "air_quality" || resolved.Triad.Resource != "mediciones" {
		t.Errorf("resolved triad mismatch: %+v", resolved.Triad)
	}
}
