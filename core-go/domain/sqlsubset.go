package domain

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// SimpleSelect is the conservative subset of SQL understood by the pure-Go
// fallback engine (InMemTabularQueryEngine):
//
//	SELECT <* | col[, col...]> FROM <table> [WHERE col = value [AND col = value ...]] [LIMIT n]
//
// Anything outside this subset (aggregations, JOIN, GROUP BY, ORDER BY,
// expressions, functions, subqueries, non-equality predicates) is rejected so
// the fallback never returns silently-wrong results. Callers needing full ANSI
// SQL must use the DuckDB engine (Python binding).
type SimpleSelect struct {
	Columns []string // nil/empty means "*"
	Table   string
	Where   map[string]string
	Limit   int
}

var (
	simpleSelectRegex   = regexp.MustCompile(`(?is)^\s*select\s+(.+?)\s+from\s+("[^"]+"|'[^']+'|[^\s;]+)(?:\s+where\s+(.+?))?(?:\s+limit\s+(\d+))?\s*;?\s*$`)
	sqlIdentifierRegex  = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_$]*$`)
	sqlNumericRegex     = regexp.MustCompile(`^[+-]?\d+(\.\d+)?$`)
	whereAndRegex       = regexp.MustCompile(`(?is)\s+and\s+`)
	whereEqRegex        = regexp.MustCompile(`^\s*([A-Za-z_][A-Za-z0-9_$]*)\s*=\s*(.+?)\s*$`)
	unsupportedSQLRegex = regexp.MustCompile(`(?is)\b(join|group\s+by|order\s+by|having|union|distinct|over|partition|case|cast|with)\b|[()]`)
)

// ParseSimpleSelect parses the supported SQL subset or explains why the statement
// is out of scope for the pure-Go fallback engine.
func ParseSimpleSelect(sqlQuery string) (*SimpleSelect, error) {
	trimmed := strings.TrimSpace(sqlQuery)
	if trimmed == "" {
		return nil, fmt.Errorf("empty SQL query")
	}
	if unsupportedSQLRegex.MatchString(trimmed) {
		return nil, unsupportedSQLError(trimmed)
	}

	m := simpleSelectRegex.FindStringSubmatch(trimmed)
	if m == nil {
		return nil, unsupportedSQLError(trimmed)
	}

	sel := &SimpleSelect{
		Table: strings.Trim(m[2], "\"'`"),
		Where: map[string]string{},
	}
	if sel.Table == "" {
		return nil, unsupportedSQLError(trimmed)
	}

	if err := parseSelectColumns(strings.TrimSpace(m[1]), sel); err != nil {
		return nil, err
	}
	if err := parseWhereClause(strings.TrimSpace(m[3]), sel); err != nil {
		return nil, err
	}
	if limitRaw := strings.TrimSpace(m[4]); limitRaw != "" {
		n, convErr := strconv.Atoi(limitRaw)
		if convErr != nil || n < 0 {
			return nil, unsupportedSQLError(trimmed)
		}
		sel.Limit = n
	}
	return sel, nil
}

func parseSelectColumns(colsRaw string, sel *SimpleSelect) error {
	if colsRaw == "*" {
		return nil
	}
	for _, raw := range strings.Split(colsRaw, ",") {
		col := strings.Trim(strings.TrimSpace(raw), "\"'`")
		if !sqlIdentifierRegex.MatchString(col) {
			return unsupportedSQLError(colsRaw)
		}
		sel.Columns = append(sel.Columns, col)
	}
	return nil
}

func parseWhereClause(whereRaw string, sel *SimpleSelect) error {
	if whereRaw == "" {
		return nil
	}
	for _, predicate := range whereAndRegex.Split(whereRaw, -1) {
		m := whereEqRegex.FindStringSubmatch(predicate)
		if m == nil {
			return unsupportedSQLError(whereRaw)
		}
		value, ok := literalValue(m[2])
		if !ok {
			return unsupportedSQLError(whereRaw)
		}
		sel.Where[strings.ToLower(m[1])] = value
	}
	return nil
}

func literalValue(raw string) (string, bool) {
	trimmed := strings.TrimSpace(raw)
	if len(trimmed) >= 2 {
		if (trimmed[0] == '\'' && trimmed[len(trimmed)-1] == '\'') ||
			(trimmed[0] == '"' && trimmed[len(trimmed)-1] == '"') {
			return trimmed[1 : len(trimmed)-1], true
		}
	}
	if sqlNumericRegex.MatchString(trimmed) {
		return trimmed, true
	}
	// A bare word value would be a column reference, which the fallback does not support.
	return "", false
}

func unsupportedSQLError(sqlQuery string) error {
	return fmt.Errorf(
		"unsupported SQL for the pure-Go fallback engine: only "+
			"SELECT <cols|*> FROM <table> [WHERE col = value [AND ...]] [LIMIT n] is supported; "+
			"use the DuckDB engine for full ANSI SQL: %q",
		sqlQuery,
	)
}
