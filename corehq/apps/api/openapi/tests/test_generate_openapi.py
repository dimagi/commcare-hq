import json
from io import StringIO

import pytest

from django.core.management import call_command
from django.core.management.base import CommandError

from corehq.apps.api.management.commands import generate_openapi
from corehq.apps.api.openapi.builder import build_all
from corehq.apps.api.management.commands.generate_openapi import (
    orphaned_specs,
    serialize,
    stale_specs,
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


def test_stale_specs_reports_a_missing_file(tmp_path):
    assert stale_specs(tmp_path, {'user-v1': {'openapi': '3.0.3'}}) == [
        'user-v1'
    ]


def test_stale_specs_reports_a_file_whose_content_drifted(tmp_path):
    document = {'openapi': '3.0.3'}
    (tmp_path / 'user-v1.json').write_text(serialize(document))
    assert stale_specs(tmp_path, {'user-v1': document}) == []

    (tmp_path / 'user-v1.json').write_text('{"openapi": "3.0.3"}')
    assert stale_specs(tmp_path, {'user-v1': document}) == ['user-v1']


def test_orphaned_specs_reports_a_stale_file_not_in_build_all(tmp_path):
    documents = build_all()
    orphan = tmp_path / 'no-longer-generated.json'
    orphan.write_text('{}')
    for name in documents:
        (tmp_path / f'{name}.json').write_text('{}')
    assert orphaned_specs(tmp_path, documents) == [orphan]


def test_orphaned_specs_is_empty_for_a_missing_directory(tmp_path):
    assert orphaned_specs(tmp_path / 'does-not-exist', build_all()) == []


# ``handle()`` itself, as opposed to the helpers above. The helpers are
# where the rules live, but the command is what CI runs, and the wiring
# between them -- which helper is consulted, what is reported, and whether
# it exits non-zero -- was previously untested. ``build_all`` is patched
# out because these check the handler's behaviour, not the generator's,
# and building every real document per case is slow.

FAKE_DOCUMENT = {'openapi': '3.0.3', 'paths': {}}


def _run_check(tmp_path, monkeypatch, documents):
    monkeypatch.setattr(generate_openapi, 'SPEC_DIR', tmp_path)
    monkeypatch.setattr(generate_openapi, 'build_all', lambda: documents)
    out = StringIO()
    call_command('generate_openapi', check=True, stdout=out)
    return out.getvalue()


def test_check_reports_success_when_every_spec_is_current(
    tmp_path, monkeypatch
):
    (tmp_path / 'thing-v1.json').write_text(serialize(FAKE_DOCUMENT))
    output = _run_check(tmp_path, monkeypatch, {'thing-v1': FAKE_DOCUMENT})
    assert 'up to date' in output


def test_check_fails_and_names_a_stale_spec(tmp_path, monkeypatch):
    (tmp_path / 'thing-v1.json').write_text('{"openapi": "3.0.3"}')
    with pytest.raises(CommandError) as excinfo:
        _run_check(tmp_path, monkeypatch, {'thing-v1': FAKE_DOCUMENT})
    message = str(excinfo.value)
    assert 'out of date: thing-v1' in message
    assert './manage.py generate_openapi' in message


def test_check_fails_and_names_an_orphaned_spec(tmp_path, monkeypatch):
    (tmp_path / 'thing-v1.json').write_text(serialize(FAKE_DOCUMENT))
    (tmp_path / 'gone-v1.json').write_text('{}')
    with pytest.raises(CommandError) as excinfo:
        _run_check(tmp_path, monkeypatch, {'thing-v1': FAKE_DOCUMENT})
    assert 'orphaned (no longer generated): gone-v1.json' in str(
        excinfo.value
    )


def test_check_reports_both_kinds_of_problem_at_once(tmp_path, monkeypatch):
    """One run should name everything wrong, not stop at the first kind."""
    (tmp_path / 'thing-v1.json').write_text('{"openapi": "3.0.3"}')
    (tmp_path / 'gone-v1.json').write_text('{}')
    with pytest.raises(CommandError) as excinfo:
        _run_check(tmp_path, monkeypatch, {'thing-v1': FAKE_DOCUMENT})
    message = str(excinfo.value)
    assert 'out of date: thing-v1' in message
    assert 'orphaned (no longer generated): gone-v1.json' in message


def test_check_writes_nothing(tmp_path, monkeypatch):
    """--check is a read-only question; a stale spec must stay stale."""
    (tmp_path / 'thing-v1.json').write_text('{"openapi": "3.0.3"}')
    with pytest.raises(CommandError):
        _run_check(tmp_path, monkeypatch, {'thing-v1': FAKE_DOCUMENT})
    assert (tmp_path / 'thing-v1.json').read_text() == '{"openapi": "3.0.3"}'


def test_the_write_path_reports_what_it_wrote_and_pruned(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(generate_openapi, 'SPEC_DIR', tmp_path)
    monkeypatch.setattr(
        generate_openapi, 'build_all', lambda: {'thing-v1': FAKE_DOCUMENT}
    )
    (tmp_path / 'gone-v1.json').write_text('{}')
    out = StringIO()
    call_command('generate_openapi', stdout=out)
    output = out.getvalue()
    assert 'wrote' in output and 'thing-v1.json' in output
    assert 'removed' in output and 'gone-v1.json' in output
    assert not (tmp_path / 'gone-v1.json').exists()
