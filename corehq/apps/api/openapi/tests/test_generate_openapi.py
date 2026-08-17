import json

from corehq.apps.api.openapi.builder import build_all
from corehq.apps.api.management.commands.generate_openapi import (
    SPEC_DIR,
    serialize,
    write_specs,
)


def test_serialize_is_deterministic_and_sorted():
    document = {'b': 1, 'a': {'d': 2, 'c': 3}}
    text = serialize(document)
    assert text.startswith('{\n')
    assert text.endswith('\n')
    assert text.index('"a"') < text.index('"b"')
    assert serialize(document) == text


def test_write_specs_writes_one_file_per_document(tmp_path):
    written = write_specs(tmp_path)
    assert {path.name for path in written} == {
        f'{name}.json' for name in build_all()
    }
    for path in written:
        json.loads(path.read_text())


def test_committed_specs_are_up_to_date():
    """Regeneration must be a no-op. If this fails, run:

    ./manage.py generate_openapi
    """
    for name, document in build_all().items():
        path = SPEC_DIR / f'{name}.json'
        assert path.exists(), f'missing committed spec: {path}'
        assert path.read_text() == serialize(document), (
            f'{path} is stale; run ./manage.py generate_openapi'
        )
