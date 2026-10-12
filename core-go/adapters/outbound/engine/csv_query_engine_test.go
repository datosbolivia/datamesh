package engine

import (
	"context"
	"path/filepath"
	"strings"
	"testing"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

func testCSVPath(t *testing.T) string {
	t.Helper()
	csvPath, err := filepath.Abs("../../../testdata/mock_data_elecciones.csv")
	if err != nil {
		t.Fatalf("resolve testdata path: %v", err)
	}
	return csvPath
}

func TestExecuteSQLProjectionFilterLimit(t *testing.T) {
	eng := NewInMemTabularQueryEngine()

	req := domain.SQLQueryRequest{
		SQLQuery: `SELECT departamento, votos_validos FROM votos WHERE departamento = 'La Paz' LIMIT 1`,
		Bindings: map[string]domain.TableBinding{
			"votos": {Name: "votos", PhysicalPath: testCSVPath(t), Format: "csv"},
		},
	}

	res, err := eng.ExecuteSQL(context.Background(), req)
	if err != nil {
		t.Fatalf("ExecuteSQL failed: %v", err)
	}
	if strings.Join(res.Columns, ",") != "departamento,votos_validos" {
		t.Errorf("expected projected columns, got %v", res.Columns)
	}
	if res.RowCount != 1 {
		t.Fatalf("expected 1 row (limit), got %d", res.RowCount)
	}
	if res.Rows[0][0] != "La Paz" || res.Rows[0][1] != "45200" {
		t.Errorf("unexpected row: %v", res.Rows[0])
	}
}

func TestExecuteSQLRejectsUnsupportedSQL(t *testing.T) {
	eng := NewInMemTabularQueryEngine()
	unsupported := []string{
		`SELECT SUM(votos_validos) FROM votos`,
		`SELECT * FROM votos ORDER BY votos_validos`,
		`SELECT DISTINCT departamento FROM votos`,
	}
	for _, sql := range unsupported {
		_, err := eng.ExecuteSQL(context.Background(), domain.SQLQueryRequest{
			SQLQuery: sql,
			Bindings: map[string]domain.TableBinding{
				"votos": {Name: "votos", PhysicalPath: testCSVPath(t), Format: "csv"},
			},
		})
		if err == nil {
			t.Errorf("expected unsupported SQL to be rejected: %q", sql)
		}
	}
}

func TestExecuteSQLRejectsAmbiguousMultiTable(t *testing.T) {
	eng := NewInMemTabularQueryEngine()
	_, err := eng.ExecuteSQL(context.Background(), domain.SQLQueryRequest{
		SQLQuery: `SELECT * FROM unknown_table`,
		Bindings: map[string]domain.TableBinding{
			"a": {Name: "a", PhysicalPath: "/nonexistent/a.csv", Format: "csv"},
			"b": {Name: "b", PhysicalPath: "/nonexistent/b.csv", Format: "csv"},
		},
	})
	if err == nil {
		t.Fatal("expected multi-table query to be rejected instead of picking a table arbitrarily")
	}
}
