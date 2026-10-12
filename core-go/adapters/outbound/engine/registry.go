package engine

import (
	"fmt"
	"sort"
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

	// Deterministic iteration order (map iteration is randomized in Go).
	ordered := r.orderedEnginesLocked()

	// 2. Multi-format cross-join requires an engine supporting cross-format joins (e.g. DuckDB)
	if len(formats) > 1 {
		for _, e := range ordered {
			if e.SupportsCrossFormatJoin() {
				return e, nil
			}
		}
	}

	// 3. Find first engine (by name) supporting all required formats
	for _, e := range ordered {
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

	// 4. Fallback to the first registered engine by name if available
	if len(ordered) > 0 {
		return ordered[0], nil
	}

	return nil, fmt.Errorf("no suitable query engine registered for formats %v", formats)
}

// orderedEnginesLocked returns the registered engines sorted by name. The caller
// must hold at least r.mu.RLock().
func (r *QueryEngineRegistry) orderedEnginesLocked() []outbound.QueryEnginePort {
	names := make([]string, 0, len(r.engines))
	for name := range r.engines {
		names = append(names, name)
	}
	sort.Strings(names)

	ordered := make([]outbound.QueryEnginePort, 0, len(names))
	for _, name := range names {
		ordered = append(ordered, r.engines[name])
	}
	return ordered
}
