package domain

import (
	"errors"
	"strings"
	"time"
)

var (
	ErrInvalidCatalogURL = errors.New("invalid or empty catalog URL")
	ErrInvalidTimeout    = errors.New("timeout must be greater than zero")
)

// BaseConfig represents core configuration parameters.
type BaseConfig struct {
	CatalogURL  string        `json:"catalog_url" yaml:"catalog_url"`
	CatalogURLs []string      `json:"catalog_urls" yaml:"catalog_urls"`
	StoragePath string        `json:"storage_path" yaml:"storage_path"`
	Timeout     time.Duration `json:"timeout" yaml:"timeout"`
	LogLevel    string        `json:"log_level" yaml:"log_level"`
}

// Config is the root configuration value object.
type Config struct {
	Base     BaseConfig                   `json:"base" yaml:"base"`
	Adapters map[string]map[string]string `json:"adapters" yaml:"adapters"`
}

// NewDefaultConfig returns a Config initialized with standard defaults.
func NewDefaultConfig() Config {
	defaultURL := "https://datosbolivia.github.io/llms.txt"
	return Config{
		Base: BaseConfig{
			CatalogURL:  defaultURL,
			CatalogURLs: []string{defaultURL},
			StoragePath: ".datamesh/cache",
			Timeout:     30 * time.Second,
			LogLevel:    "info",
		},
		Adapters: make(map[string]map[string]string),
	}
}

// Validate checks business invariants of the configuration.
func (c Config) Validate() error {
	if strings.TrimSpace(c.Base.CatalogURL) == "" {
		return ErrInvalidCatalogURL
	}
	if c.Base.Timeout <= 0 {
		return ErrInvalidTimeout
	}
	return nil
}

// GetAdapterValue safely retrieves an adapter-specific configuration option.
func (c Config) GetAdapterValue(adapterName, key string) (string, bool) {
	if c.Adapters == nil {
		return "", false
	}
	adapter, exists := c.Adapters[strings.ToLower(adapterName)]
	if !exists {
		return "", false
	}
	val, ok := adapter[strings.ToLower(key)]
	return val, ok
}

// redactSensitiveKeys masks adapter values that look like secrets (tokens,
// API keys, passwords) so that serialized configuration never leaks them.
func redactSensitiveKeys(c Config) Config {
	sanitized := NewDefaultConfig()
	sanitized.Base = c.Base
	sanitized.Adapters = make(map[string]map[string]string, len(c.Adapters))
	for adapter, kv := range c.Adapters {
		out := make(map[string]string, len(kv))
		for key, value := range kv {
			lk := strings.ToLower(key)
			switch {
			case strings.Contains(lk, "token"),
				strings.Contains(lk, "secret"),
				strings.Contains(lk, "password"),
				strings.Contains(lk, "passwd"),
				strings.Contains(lk, "credential"),
				strings.Contains(lk, "api_key"),
				strings.Contains(lk, "apikey"),
				strings.Contains(lk, "client_secret"):
				out[key] = "***"
			default:
				out[key] = value
			}
		}
		sanitized.Adapters[adapter] = out
	}
	return sanitized
}

// Sanitized returns a copy of the configuration safe for logging or
// serialization: adapter secrets (tokens, keys, passwords) are masked.
func (c Config) Sanitized() Config {
	return redactSensitiveKeys(c)
}
