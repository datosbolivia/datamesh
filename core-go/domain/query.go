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

// SQLQueryRequest encapsulates a full ANSI/DuckDB SQL query with unresolved or resolved triads.
type SQLQueryRequest struct {
	SQLQuery       string                      `json:"sql_query"`
	Triads         []ResourceTriad             `json:"triads,omitempty"`
	ResolvedTables map[string]ResolvedResource `json:"resolved_tables,omitempty"`
}

// QueryResult encapsulates the tabular dataset resulting from a query execution.
type QueryResult struct {
	Columns       []string        `json:"columns"`
	Rows          [][]interface{} `json:"rows"`
	RowCount      int             `json:"row_count"`
	ExecutionTime time.Duration   `json:"execution_time"`
}

// NewQueryResult initializes a result with row count.
func NewQueryResult(columns []string, rows [][]interface{}, elapsed time.Duration) *QueryResult {
	return &QueryResult{
		Columns:       columns,
		Rows:          rows,
		RowCount:      len(rows),
		ExecutionTime: elapsed,
	}
}
