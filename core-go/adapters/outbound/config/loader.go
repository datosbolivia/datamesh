package config

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// FileAndEnvConfigLoader loads configuration prioritizing Environment Variables > File Config > Defaults.
type FileAndEnvConfigLoader struct {
	envLookup func(string) []string
}

// NewConfigLoader returns an initialized configuration loader.
func NewConfigLoader() *FileAndEnvConfigLoader {
	return &FileAndEnvConfigLoader{
		envLookup: os.Environ,
	}
}

// Load resolves configuration starting from defaults, overlaying file contents, and overriding with env vars.
func (l *FileAndEnvConfigLoader) Load(explicitPath string) (domain.Config, error) {
	cfg := domain.NewDefaultConfig()

	// 1. Locate config file if exists
	filePath := explicitPath
	if filePath == "" {
		candidates := []string{"datamesh.json", "datamesh.yaml", "datamesh.yml"}
		for _, cand := range candidates {
			if _, err := os.Stat(cand); err == nil {
				filePath = cand
				break
			}
		}
	}

	if filePath != "" {
		if err := l.loadFile(filePath, &cfg); err != nil && !os.IsNotExist(err) {
			return cfg, err
		}
	}

	// 2. Overlay environment variables
	l.overlayEnvVars(&cfg)

	return cfg, nil
}

func (l *FileAndEnvConfigLoader) loadFile(path string, cfg *domain.Config) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}

	ext := strings.ToLower(filepath.Ext(path))
	if ext == ".json" {
		var raw struct {
			CatalogURL  string                       `json:"catalog_url"`
			StoragePath string                       `json:"storage_path"`
			Timeout     int                          `json:"timeout"`
			LogLevel    string                       `json:"log_level"`
			Adapters    map[string]map[string]string `json:"adapters"`
		}
		if err := json.Unmarshal(data, &raw); err != nil {
			return err
		}
		if raw.CatalogURL != "" {
			cfg.Base.CatalogURL = raw.CatalogURL
		}
		if raw.StoragePath != "" {
			cfg.Base.StoragePath = raw.StoragePath
		}
		if raw.Timeout > 0 {
			cfg.Base.Timeout = time.Duration(raw.Timeout) * time.Second
		}
		if raw.LogLevel != "" {
			cfg.Base.LogLevel = raw.LogLevel
		}
		if raw.Adapters != nil {
			for adp, kv := range raw.Adapters {
				k := strings.ToLower(adp)
				if cfg.Adapters[k] == nil {
					cfg.Adapters[k] = make(map[string]string)
				}
				for key, val := range kv {
					cfg.Adapters[k][strings.ToLower(key)] = val
				}
			}
		}
		return nil
	}

	// Simple YAML / YML line parser (KISS, zero-dependency)
	return parseSimpleYAML(string(data), cfg)
}

func parseSimpleYAML(content string, cfg *domain.Config) error {
	scanner := bufio.NewScanner(strings.NewReader(content))
	currentSection := ""
	currentAdapter := ""

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		// Detect root sections
		if strings.HasSuffix(line, ":") {
			sec := strings.TrimSuffix(line, ":")
			if sec == "adapters" {
				currentSection = "adapters"
				currentAdapter = ""
				continue
			}
			if currentSection == "adapters" {
				currentAdapter = strings.ToLower(sec)
				if cfg.Adapters[currentAdapter] == nil {
					cfg.Adapters[currentAdapter] = make(map[string]string)
				}
				continue
			}
		}

		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.Trim(strings.TrimSpace(parts[1]), "\"'")

		if currentSection == "adapters" && currentAdapter != "" {
			cfg.Adapters[currentAdapter][strings.ToLower(key)] = val
			continue
		}

		switch strings.ToLower(key) {
		case "catalog_url":
			cfg.Base.CatalogURL = val
		case "storage_path":
			cfg.Base.StoragePath = val
		case "timeout":
			if secs, err := strconv.Atoi(val); err == nil && secs > 0 {
				cfg.Base.Timeout = time.Duration(secs) * time.Second
			}
		case "log_level":
			cfg.Base.LogLevel = val
		}
	}
	return scanner.Err()
}

func (l *FileAndEnvConfigLoader) overlayEnvVars(cfg *domain.Config) {
	for _, env := range l.envLookup() {
		pair := strings.SplitN(env, "=", 2)
		if len(pair) != 2 {
			continue
		}
		k, v := pair[0], pair[1]

		if !strings.HasPrefix(k, "DATAMESH_") {
			continue
		}

		// Check for adapter-specific variable: DATAMESH__{ADAPTER}_{VAR} or DATAMESH__{ADAPTER}__{VAR}
		if strings.HasPrefix(k, "DATAMESH__") {
			afterPrefix := strings.TrimPrefix(k, "DATAMESH__")
			// Split by double underscore or first single underscore
			var adapter, key string
			if strings.Contains(afterPrefix, "__") {
				adpParts := strings.SplitN(afterPrefix, "__", 2)
				adapter = strings.ToLower(adpParts[0])
				key = strings.ToLower(adpParts[1])
			} else {
				adpParts := strings.SplitN(afterPrefix, "_", 2)
				if len(adpParts) == 2 {
					adapter = strings.ToLower(adpParts[0])
					key = strings.ToLower(adpParts[1])
				}
			}

			if adapter != "" && key != "" {
				if cfg.Adapters[adapter] == nil {
					cfg.Adapters[adapter] = make(map[string]string)
				}
				cfg.Adapters[adapter][key] = v
			}
			continue
		}

		// Base configuration: DATAMESH_{VAR}
		baseKey := strings.ToLower(strings.TrimPrefix(k, "DATAMESH_"))
		switch baseKey {
		case "catalog_url":
			cfg.Base.CatalogURL = v
		case "storage_path":
			cfg.Base.StoragePath = v
		case "timeout":
			if secs, err := strconv.Atoi(v); err == nil && secs > 0 {
				cfg.Base.Timeout = time.Duration(secs) * time.Second
			}
		case "log_level":
			cfg.Base.LogLevel = v
		}
	}
}
