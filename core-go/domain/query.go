package domain

import (
	"time"
)

// QueryRequest specifies a tabular query targeting a Data Product resource.
type QueryRequest struct {
	ResourceURI string            `json:"resource_uri"`
	Query       string            `json:"query"`
	Filters     map[string]string `json:"filters,omitempty"`
	Limit       int               `json:"limit,omitempty"`
}

// TableBinding defines a table name mapped to a physical resource and format.
type TableBinding struct {
	Name         string   `json:"name"`
	PhysicalPath string   `json:"physical_path"`
	Format       string   `json:"format"` // parquet, csv, tsv, json, jsonl
	Aliases      []string `json:"aliases,omitempty"`
}

// QueryOptions configures engine selection, timeouts, and table overrides.
type QueryOptions struct {
	Timeout      time.Duration     `json:"timeout,omitempty"`
	MaxRows      int               `json:"max_rows,omitempty"`
	EngineName   string            `json:"engine_name,omitempty"` // "duckdb", "inmem", "auto"
	TableMapping map[string]string `json:"table_mapping,omitempty"`
}

// SQLQueryRequest encapsulates a full ANSI/DuckDB SQL query with unresolved or resolved triads.
type SQLQueryRequest struct {
	SQLQuery       string                      `json:"sql_query"`
	Triads         []ResourceTriad             `json:"triads,omitempty"`
	ResolvedTables map[string]ResolvedResource `json:"resolved_tables,omitempty"`
	Bindings       map[string]TableBinding     `json:"bindings,omitempty"`
	Options        QueryOptions                `json:"options,omitempty"`
}

// QueryResult encapsulates the tabular dataset resulting from a query execution.
type QueryResult struct {
	Columns       []string        `json:"columns"`
	Rows          [][]interface{} `json:"rows"`
	RowCount      int             `json:"row_count"`
	ExecutionTime time.Duration   `json:"execution_time"`
	EngineUsed    string          `json:"engine_used,omitempty"`
}

// NewQueryResult initializes a result with row count.
func NewQueryResult(columns []string, rows [][]interface{}, elapsed time.Duration) *QueryResult {
	return &QueryResult{
		Columns:       columns,
		Rows:          rows,
		RowCount:      len(rows),
		ExecutionTime: elapsed,
		EngineUsed:    "inmem",
	}
}
