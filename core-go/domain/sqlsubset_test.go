package domain

import "testing"

func TestParseSimpleSelectValid(t *testing.T) {
	cases := []struct {
		sql   string
		cols  []string
		table string
		where map[string]string
		limit int
	}{
		{`SELECT * FROM "bolivia:elecciones:votos_2020"`, nil, "bolivia:elecciones:votos_2020", map[string]string{}, 0},
		{`SELECT departamento, votos_validos FROM votos`, []string{"departamento", "votos_validos"}, "votos", map[string]string{}, 0},
		{`SELECT departamento FROM votos WHERE departamento = 'La Paz' LIMIT 5`, []string{"departamento"}, "votos", map[string]string{"departamento": "La Paz"}, 5},
		{`select * from t where a = 1 and b = 'x'`, nil, "t", map[string]string{"a": "1", "b": "x"}, 0},
	}

	for _, tc := range cases {
		sel, err := ParseSimpleSelect(tc.sql)
		if err != nil {
			t.Fatalf("unexpected error for %q: %v", tc.sql, err)
		}
		if sel.Table != tc.table {
			t.Errorf("%q: table = %q, want %q", tc.sql, sel.Table, tc.table)
		}
		if len(sel.Columns) != len(tc.cols) {
			t.Errorf("%q: columns = %v, want %v", tc.sql, sel.Columns, tc.cols)
		} else {
			for i := range tc.cols {
				if sel.Columns[i] != tc.cols[i] {
					t.Errorf("query %q: column %d = %q, want %q", tc.sql, i, sel.Columns[i], tc.cols[i])
				}
			}
		}
		if len(sel.Where) != len(tc.where) {
			t.Errorf("query %q: where %v, want %v", tc.sql, sel.Where, tc.where)
		}
		for k, v := range tc.where {
			if sel.Where[k] != v {
				t.Errorf("query %q: where[%q] = %q, want %q", tc.sql, k, sel.Where[k], v)
			}
		}
		if sel.Limit != tc.limit {
			t.Errorf("query %q: limit %d, want %d", tc.sql, sel.Limit, tc.limit)
		}
	}
}

func TestParseSimpleSelectRejectsUnsupported(t *testing.T) {
	unsupported := []string{
		``,
		`SELECT SUM(votos_validos) FROM votos`,
		`SELECT * FROM a JOIN b ON a.x = b.x`,
		`SELECT departamento FROM votos GROUP BY departamento`,
		`SELECT * FROM votos ORDER BY votos_validos DESC`,
		`SELECT DISTINCT departamento FROM votos`,
		`SELECT * FROM votos WHERE votos_validos > 100`,
		`DELETE FROM votos`,
		`SELECT departamento, COUNT(*) FROM votos`,
	}
	for _, sql := range unsupported {
		if _, err := ParseSimpleSelect(sql); err == nil {
			t.Errorf("expected unsupported SQL to be rejected: %q", sql)
		}
	}
}
