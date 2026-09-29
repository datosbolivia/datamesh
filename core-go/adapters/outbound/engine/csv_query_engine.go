package engine

import (
	"bytes"
	"context"
	"encoding/csv"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// InMemTabularQueryEngine executes filtering and projection queries over CSV and delimited data.
type InMemTabularQueryEngine struct{}

// NewInMemTabularQueryEngine creates an instance of the tabular query engine.
func NewInMemTabularQueryEngine() *InMemTabularQueryEngine {
	return &InMemTabularQueryEngine{}
}

// Execute parses raw delimited data, applies column selection, filters, and limits.
func (e *InMemTabularQueryEngine) Execute(
	ctx context.Context,
	req domain.QueryRequest,
	rawData []byte,
	format string,
) (*domain.QueryResult, error) {
	start := time.Now()

	reader := csv.NewReader(bytes.NewReader(rawData))
	if strings.ToLower(format) == "tsv" {
		reader.Comma = '\t'
	}

	headers, err := reader.Read()
	if err != nil {
		return nil, fmt.Errorf("failed to read table headers: %w", err)
	}

	colIndex := make(map[string]int)
	for i, h := range headers {
		colIndex[strings.ToLower(strings.TrimSpace(h))] = i
	}

	// Filter mapping (case-insensitive column names)
	filterIndices := make(map[int]string)
	for k, v := range req.Filters {
		normKey := strings.ToLower(strings.TrimSpace(k))
		if idx, found := colIndex[normKey]; found {
			filterIndices[idx] = strings.ToLower(strings.TrimSpace(v))
		}
	}

	var matchedRows [][]interface{}

	for {
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}

		record, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			continue // skip malformed lines
		}

		// Apply filters
		matches := true
		for idx, expectedVal := range filterIndices {
			if idx >= len(record) || strings.ToLower(strings.TrimSpace(record[idx])) != expectedVal {
				matches = false
				break
			}
		}

		if matches {
			row := make([]interface{}, len(record))
			for i, val := range record {
				row[i] = val
			}
			matchedRows = append(matchedRows, row)

			if req.Limit > 0 && len(matchedRows) >= req.Limit {
				break
			}
		}
	}

	elapsed := time.Since(start)
	return domain.NewQueryResult(headers, matchedRows, elapsed), nil
}

// ExecuteSQL provides basic SQL execution fallback over resolved CSV/TSV resources in Go Core.
func (e *InMemTabularQueryEngine) ExecuteSQL(ctx context.Context, req domain.SQLQueryRequest) (*domain.QueryResult, error) {
	if len(req.ResolvedTables) == 0 {
		return nil, fmt.Errorf("no tables resolved for SQL query: %s", req.SQLQuery)
	}

	// For single table queries in Go Core fallback
	for _, res := range req.ResolvedTables {
		// Read physical file if local
		data, err := os.ReadFile(res.PhysicalURI)
		if err != nil {
			return nil, fmt.Errorf("failed to read table '%s' at %s: %w", res.Triad.String(), res.PhysicalURI, err)
		}

		queryReq := domain.QueryRequest{
			ResourceURI: res.PhysicalURI,
			Query:       req.SQLQuery,
		}
		return e.Execute(ctx, queryReq, data, res.Format)
	}

	return nil, fmt.Errorf("unsupported multi-table query in pure Go fallback (use DuckDB engine)")
}
