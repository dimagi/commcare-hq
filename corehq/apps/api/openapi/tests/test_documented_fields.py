from corehq.apps.api.openapi.catalogue import documented_entries
from corehq.apps.api.openapi.docs import collect_docs, field_description

# Slugs whose fields must all carry a real description. Add a slug here when
# its documentation is written; do not remove one.
DOCUMENTED_SLUGS = frozenset({'user-v1'})


def _undocumented_fields(entry):
    resource = entry.resource(api_name=entry.version)
    schema = resource.build_schema()
    overrides = collect_docs(entry.resource).get('field_schemas', {})
    return sorted(
        name
        for name, info in schema['fields'].items()
        if not field_description(info.get('help_text'))
        and 'description' not in overrides.get(name, {})
    )


def test_every_field_of_documented_apis_has_a_description():
    failures = {}
    for entry in documented_entries():
        if entry.doc_slug not in DOCUMENTED_SLUGS:
            continue
        undocumented = _undocumented_fields(entry)
        if undocumented:
            failures[entry.doc_slug] = undocumented
    assert not failures, (
        'These fields need help_text (or a Docs.field_schemas description): '
        f'{failures}'
    )


def test_documented_apis_declare_a_summary_and_description():
    for entry in documented_entries():
        if entry.doc_slug not in DOCUMENTED_SLUGS:
            continue
        docs = collect_docs(entry.resource)
        assert docs.get('summary'), f'{entry.doc_slug} needs a Docs.summary'
        assert docs.get('description'), (
            f'{entry.doc_slug} needs a Docs.description'
        )


def test_declared_examples_exist_on_disk():
    from pathlib import Path

    from corehq.apps.api import openapi

    examples_dir = Path(openapi.__file__).parent / 'examples'
    for entry in documented_entries():
        for name, relative in (
            collect_docs(entry.resource).get('examples', {}).items()
        ):
            assert (examples_dir / relative).exists(), (
                f'{entry.doc_slug} example {name!r} missing: {relative}'
            )
