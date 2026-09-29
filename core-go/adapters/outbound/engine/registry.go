package engine

import (
	"fmt"
	"strings"
	"sync"

	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// QueryEngineRegistry manages multiple concrete query engine adapters.
type QueryEngineRegistry struct {
	mu      sync.RWMutex
	engines map[string]outbound.QueryEnginePort
}

// NewQueryEngineRegistry initializes an empty or defaulted registry.
func NewQueryEngineRegistry(defaultEngines ...outbound.QueryEnginePort) *QueryEngineRegistry {
	reg := &QueryEngineRegistry{
		engines: make(map[string]outbound.QueryEnginePort),
	}
	for _, e := range defaultEngines {
		reg.RegisterEngine(e)
	}
	return reg
}

// RegisterEngine adds an engine to the registry.
func (r *QueryEngineRegistry) RegisterEngine(engine outbound.QueryEnginePort) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.engines[strings.ToLower(engine.Name())] = engine
}

// GetEngine retrieves an engine by its registered name.
func (r *QueryEngineRegistry) GetEngine(name string) (outbound.QueryEnginePort, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	e, exists := r.engines[strings.ToLower(name)]
	return e, exists
}

// SelectEngine selects an appropriate engine based on preference and required formats.
func (r *QueryEngineRegistry) SelectEngine(preferred string, formats []string) (outbound.QueryEnginePort, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	// 1. Explicit preference match
	if preferred != "" && preferred != "auto" {
		if e, exists := r.engines[strings.ToLower(preferred)]; exists {
			return e, nil
		}
	}

	// 2. Multi-format cross-join requires an engine supporting cross-format joins (e.g. DuckDB)
	if len(formats) > 1 {
		for _, e := range r.engines {
			if e.SupportsCrossFormatJoin() {
				return e, nil
			}
		}
	}

	// 3. Find first engine supporting all required formats
	for _, e := range r.engines {
		allSupported := true
		for _, fmtStr := range formats {
			if !e.SupportsFormat(fmtStr) {
				allSupported = false
				break
			}
		}
		if allSupported {
			return e, nil
		}
	}

	// 4. Fallback to any registered engine if available
	for _, e := range r.engines {
		return e, nil
	}

	return nil, fmt.Errorf("no suitable query engine registered for formats %v", formats)
}
