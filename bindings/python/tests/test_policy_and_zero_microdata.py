import os
import pytest
from datamesh.adapters.engine.duckdb_engine import DuckDBQueryEngine
from datamesh.adapters.go_bridge import GoCoreBridge
from datamesh.domain.errors import PolicyViolationError


def test_zero_microdata_enforcement(tmp_path):
    csv_file = tmp_path / "censo.csv"
    csv_file.write_text("id,departamento,votos\n1,La Paz,100\n2,Cochabamba,200\n3,Santa Cruz,300\n")

    engine = DuckDBQueryEngine()
    engine.register_table("bolivia:censo:personas", str(csv_file))
    engine.set_table_policy("bolivia:censo:personas", "zero_microdata")

    # 1. SELECT * must fail with PolicyViolationError
    with pytest.raises(PolicyViolationError) as exc_info:
        engine.execute_sql("SELECT * FROM 'bolivia:censo:personas'")
    assert "zero_microdata" in str(exc_info.value).lower()

    # 2. Aggregations (COUNT, GROUP BY) must succeed
    res = engine.execute_sql(
        "SELECT departamento, COUNT(*), SUM(votos) FROM 'bolivia:censo:personas' GROUP BY departamento"
    )
    assert res["row_count"] == 3
    assert len(res["columns"]) == 3

    # 3. Privileged identity (analyst / admin) must be allowed
    privileged_mapping = {
        "__identity__": {"role": "analyst", "trust_tier": "official"}
    }
    raw_res = engine.execute_sql("SELECT * FROM 'bolivia:censo:personas'", table_mapping=privileged_mapping)
    assert raw_res["row_count"] == 3


def test_deny_policy_enforcement(tmp_path):
    csv_file = tmp_path / "secret.csv"
    csv_file.write_text("a,b\n1,2\n")

    engine = DuckDBQueryEngine()
    engine.register_table("secret_data", str(csv_file))
    engine.set_table_policy("secret_data", "deny")

    # Public user denied
    with pytest.raises(PolicyViolationError) as exc_info:
        engine.execute_sql("SELECT COUNT(*) FROM secret_data")
    assert "deny" in str(exc_info.value).lower()

    # Admin user allowed
    admin_mapping = {"__identity__": {"role": "admin"}}
    res = engine.execute_sql("SELECT COUNT(*) FROM secret_data", table_mapping=admin_mapping)
    assert res["row_count"] == 1


def test_go_bridge_policy_evaluation():
    bridge = GoCoreBridge("/tmp/libdatamesh.so")
    if not bridge.available:
        pytest.skip("libdatamesh.so not compiled at /tmp/libdatamesh.so")

    # Evaluate allow_all
    decision = bridge.evaluate_policy("allow_all", "SELECT * FROM 'table'")
    assert decision["allowed"] is True

    # Evaluate zero_microdata on select star
    decision_star = bridge.evaluate_policy("zero_microdata", "SELECT * FROM 'censo'")
    assert decision_star["allowed"] is False
    assert decision_star["policy"] == "zero_microdata"

    # Evaluate zero_microdata on count group by
    decision_agg = bridge.evaluate_policy("zero_microdata", "SELECT dept, COUNT(*) FROM 'censo' GROUP BY dept")
    assert decision_agg["allowed"] is True
