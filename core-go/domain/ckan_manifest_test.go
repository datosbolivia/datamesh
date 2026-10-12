package domain

import "testing"

func TestReconstructManifestFromCKANHandlesShortResourceIDs(t *testing.T) {
	pkg := &CKANPackage{
		Name:  "votos-2020",
		Title: "Votos 2020",
		Resources: []CKANResource{
			{ID: "", Name: "", URL: "https://example.org/a.csv", Format: "CSV"},
			{ID: "ab", Name: "", URL: "https://example.org/b.csv", Format: "csv"},
			{ID: "abcdefghijklmnop", Name: "", URL: "https://example.org/c.csv", Format: "csv"},
			{ID: "ignored", Name: "Padron", URL: "https://example.org/d.csv", Format: "csv"},
		},
	}

	manifest, err := ReconstructManifestFromCKAN(pkg)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(manifest.Resources) != 4 {
		t.Fatalf("expected 4 resources, got %d", len(manifest.Resources))
	}

	wantNames := []string{"resource", "resource_ab", "resource_abcdefgh", "padron"}
	for i, want := range wantNames {
		if manifest.Resources[i].Name != want {
			t.Errorf("resource %d name = %q, want %q", i, manifest.Resources[i].Name, want)
		}
	}
}

func TestReconstructManifestFromCKANNilPackage(t *testing.T) {
	if _, err := ReconstructManifestFromCKAN(nil); err == nil {
		t.Fatal("expected error for nil CKAN package")
	}
}
