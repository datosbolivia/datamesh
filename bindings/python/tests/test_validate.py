import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import datamesh as dm

def test_validate_triad_syntax():
    res = dm.validate("bolivia:elecciones:votos")
    assert res["valid"] is True
    assert res["total_errors"] == 0

def test_validate_slash_triad():
    res = dm.validate("bolivia/elecciones/votos")
    assert res["valid"] is True
    assert res["total_errors"] == 0

def test_validate_invalid_syntax():
    res = dm.validate("invalid")
    assert res["valid"] is False
    assert res["total_errors"] > 0
