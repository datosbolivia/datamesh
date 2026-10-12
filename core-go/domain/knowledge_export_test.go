package domain

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func exporterFixture() *DataProduct {
	ts, err := time.Parse(time.RFC3339, "2026-01-15T10:00:00Z")
	if err != nil {
		panic(err)
	}
	dp, err := NewDataProduct("inseguridad-alimentaria", Manifest{
		Type:       "dataset",
		Title:      "Inseguridad alimentaria",
		Dimensions: []string{"tema", "ubi_geo"},
		Nature:     "structured",
		Status:     "verified",
		Lineage: Lineage{
			Version:   "2.0.1",
			UpdatedAt: ts,
			Emitter:   &EpistemicActor{By: "human:ine", At: ts},
		},
		Spatial: &SpatialCoverage{Country: "BO", Granularity: "country"},
		Temporal: &TemporalCoverage{Frequency: "monthly"},
	}, "dataset con cobertura temporal mensual.",
		[]Resource{{Name: "indicadores", Path: "https://datos.bo/fa.csv", Format: "csv", HashSHA256: "abc123"}})
	if err != nil {
		panic(err)
	}
	return dp
}

func TestToCKANDataPackageJSON_PreservesODKFExtras(t *testing.T) {
	raw, err := exporterFixture().ToCKANDataPackageJSON()
	if err != nil {
		t.Fatalf("ToCKANDataPackageJSON error: %v", err)
	}
	var out map[string]interface{}
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	extras, ok := out["extras"].(map[string]interface{})
	if !ok {
		t.Fatalf("extras missing: %s", raw)
	}
	if extras["status"] != "verified" {
		t.Fatalf("status not exported: %v", extras["status"])
	}
	if extras["emitter"] != "human:ine" {
		t.Fatalf("emitter not exported: %v", extras["emitter"])
	}
	spatial, ok := extras["spatial"].(map[string]interface{})
	if !ok || spatial["country"] != "BO" {
		t.Fatalf("spatial not exported: %v", extras["spatial"])
	}
	res, ok := out["resources"].([]interface{})
	if !ok || len(res) != 1 {
		t.Fatalf("resources not exported: %v", out["resources"])
	}
	r := res[0].(map[string]interface{})
	if r["hash"] != "abc123" || r["format"] != "csv" {
		t.Fatalf("resource fields wrong: %v", r)
	}
}

func TestToDCATJSON_KeywordsAndDistribution(t *testing.T) {
	raw, err := exporterFixture().ToDCATJSON()
	if err != nil {
		t.Fatalf("ToDCATJSON error: %v", err)
	}
	var out DCATDatasetJSON
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if len(out.Keywords) != 2 || !strings.Contains(out.Title, "alimentaria") {
		t.Fatalf("keywords/title wrong: %+v", out)
	}
	if out.Modified != "2026-01-15T10:00:00Z" {
		t.Fatalf("modified timestamp wrong: %+v", out.Modified)
	}
	if len(out.Distribution) != 1 || out.Distribution[0].Format != "csv" {
		t.Fatalf("distribution wrong: %+v", out.Distribution)
	}
}