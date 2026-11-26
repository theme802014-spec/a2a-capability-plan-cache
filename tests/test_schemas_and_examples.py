import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]


def load_example(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "examples" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixtures_validate_against_published_schemas(monkeypatch):
    # sibling import is only used by CLI demos, not the runtime package
    monkeypatch.syspath_prepend(str(ROOT / "examples"))
    module = load_example("run_demo")
    entry, current, _ = module.fixtures()
    registry = Registry()
    schemas = {}
    for path in (ROOT / "schemas").glob("*.json"):
        schema = json.loads(path.read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        uri = "https://schemas.invalid/" + path.name
        registry = registry.with_resource(uri, Resource.from_contents(schema))
        schemas[path.name] = {"$id": uri, **schema}
    validator = jsonschema.Draft202012Validator(schemas["plan-cache-entry.schema.json"], registry=registry)
    validator.validate(entry)
    bad = dict(entry, revision=0)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(bad)


def test_lifecycle_demo_has_no_automatic_replanning(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "examples"))
    rows = load_example("lifecycle_demo").run(tmp_path / "demo.db")
    assert rows[2]["reuse"] is True
    assert rows[3]["reuse"] is False
    assert rows[-1]["queue"]["automatic_replanning"] is False
