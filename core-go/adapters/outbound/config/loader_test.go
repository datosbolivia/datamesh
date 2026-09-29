package config

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestDefaultConfig(t *testing.T) {
	loader := NewConfigLoader()
	cfg, err := loader.Load("")
	if err != nil {
		t.Fatalf("unexpected error loading default config: %v", err)
	}

	if cfg.Base.CatalogURL != "https://datosbolivia.github.io/llms.txt" {
		t.Errorf("expected default catalog URL, got %s", cfg.Base.CatalogURL)
	}
	if cfg.Base.Timeout != 30*time.Second {
		t.Errorf("expected 30s timeout, got %v", cfg.Base.Timeout)
	}
}

func TestEnvVarBaseAndAdapterOverrides(t *testing.T) {
	loader := &FileAndEnvConfigLoader{
		envLookup: func() []string {
			return []string{
				"DATAMESH_CATALOG_URL=https://custom.org/llms.txt",
				"DATAMESH_TIMEOUT=45",
				"DATAMESH__KAGGLE_KEY=secret_key_123",
				"DATAMESH__KAGGLE_USERNAME=datatester",
				"DATAMESH__GITHUB__TOKEN=ghp_token_xyz",
				"OTHER_VAR=ignore_me",
			}
		},
	}

	cfg, err := loader.Load("")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Base overrides
	if cfg.Base.CatalogURL != "https://custom.org/llms.txt" {
		t.Errorf("expected overridden catalog URL, got %s", cfg.Base.CatalogURL)
	}
	if cfg.Base.Timeout != 45*time.Second {
		t.Errorf("expected 45s timeout, got %v", cfg.Base.Timeout)
	}

	// Adapter overrides
	kaggleKey, ok := cfg.GetAdapterValue("kaggle", "key")
	if !ok || kaggleKey != "secret_key_123" {
		t.Errorf("expected kaggle key 'secret_key_123', got %s (ok=%v)", kaggleKey, ok)
	}

	kaggleUser, ok := cfg.GetAdapterValue("kaggle", "username")
	if !ok || kaggleUser != "datatester" {
		t.Errorf("expected kaggle username 'datatester', got %s", kaggleUser)
	}

	ghToken, ok := cfg.GetAdapterValue("github", "token")
	if !ok || ghToken != "ghp_token_xyz" {
		t.Errorf("expected github token 'ghp_token_xyz', got %s", ghToken)
	}
}

func TestJSONAndYAMLConfigFile(t *testing.T) {
	tmpDir := t.TempDir()

	// 1. JSON test
	jsonPath := filepath.Join(tmpDir, "datamesh.json")
	jsonContent := `{
		"catalog_url": "https://json-catalog.org/llms.txt",
		"timeout": 15,
		"adapters": {
			"kaggle": {
				"key": "json_kaggle_key"
			}
		}
	}`
	if err := os.WriteFile(jsonPath, []byte(jsonContent), 0644); err != nil {
		t.Fatal(err)
	}

	loader := &FileAndEnvConfigLoader{
		envLookup: func() []string { return nil },
	}
	cfg, err := loader.Load(jsonPath)
	if err != nil {
		t.Fatalf("failed to load JSON config: %v", err)
	}
	if cfg.Base.CatalogURL != "https://json-catalog.org/llms.txt" {
		t.Errorf("JSON catalog URL mismatch: got %s", cfg.Base.CatalogURL)
	}
	if cfg.Base.Timeout != 15*time.Second {
		t.Errorf("JSON timeout mismatch: got %v", cfg.Base.Timeout)
	}
	if val, _ := cfg.GetAdapterValue("kaggle", "key"); val != "json_kaggle_key" {
		t.Errorf("JSON adapter value mismatch: got %s", val)
	}

	// 2. YAML test
	yamlPath := filepath.Join(tmpDir, "datamesh.yaml")
	yamlContent := `catalog_url: https://yaml-catalog.org/llms.txt
timeout: 60
log_level: debug
adapters:
  kaggle:
    key: yaml_kaggle_key
`
	if err := os.WriteFile(yamlPath, []byte(yamlContent), 0644); err != nil {
		t.Fatal(err)
	}

	cfgYAML, err := loader.Load(yamlPath)
	if err != nil {
		t.Fatalf("failed to load YAML config: %v", err)
	}
	if cfgYAML.Base.CatalogURL != "https://yaml-catalog.org/llms.txt" {
		t.Errorf("YAML catalog URL mismatch: got %s", cfgYAML.Base.CatalogURL)
	}
	if cfgYAML.Base.Timeout != 60*time.Second {
		t.Errorf("YAML timeout mismatch: got %v", cfgYAML.Base.Timeout)
	}
	if val, _ := cfgYAML.GetAdapterValue("kaggle", "key"); val != "yaml_kaggle_key" {
		t.Errorf("YAML adapter value mismatch: got %s", val)
	}
}
