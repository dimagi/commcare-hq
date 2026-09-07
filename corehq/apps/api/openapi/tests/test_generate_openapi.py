import json

from corehq.apps.api.openapi.builder import build_all
from corehq.apps.api.management.commands.generate_openapi import (
    SPEC_DIR,
    orphaned_specs,
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
    written, pruned = write_specs(tmp_path)
    assert {path.name for path in written} == {
        f'{name}.json' for name in build_all()
    }
    assert pruned == []
    for path in written:
        json.loads(path.read_text())


def test_write_specs_prunes_a_spec_no_longer_generated(tmp_path):
    """Renaming or removing a doc_slug must not leave its old spec file
    committed and still rendering."""
    orphan = tmp_path / 'no-longer-generated.json'
    orphan.write_text('{}')
    written, pruned = write_specs(tmp_path)
    assert not orphan.exists()
    assert pruned == [orphan]
    assert orphan.name not in {path.name for path in written}


def test_orphaned_specs_reports_a_stale_file_not_in_build_all(tmp_path):
    documents = build_all()
    orphan = tmp_path / 'no-longer-generated.json'
    orphan.write_text('{}')
    for name in documents:
        (tmp_path / f'{name}.json').write_text('{}')
    assert orphaned_specs(tmp_path, documents) == [orphan]


def test_orphaned_specs_is_empty_for_a_missing_directory(tmp_path):
    assert orphaned_specs(tmp_path / 'does-not-exist', build_all()) == []


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
