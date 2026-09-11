import pytest

from corehq.apps.api.openapi.catalogue import documented_view_entries
from corehq.apps.api.openapi.examples import EXAMPLES_DIR
from corehq.apps.api.openapi.view_operations import (
    example_key,
    operations_served,
)

VIEW_ENTRIES = documented_view_entries()


def _docs(entry):
    return entry.resolve()._openapi_docs


@pytest.mark.parametrize('entry', VIEW_ENTRIES, ids=lambda e: e.view)
def test_documented_views_declare_a_summary_and_description(entry):
    docs = _docs(entry)
    assert docs.summary, f'{entry.view} needs a summary'
    assert docs.description, f'{entry.view} needs a description'


@pytest.mark.parametrize('entry', VIEW_ENTRIES, ids=lambda e: e.view)
def test_declared_view_examples_exist_on_disk(entry):
    missing = sorted(
        str(relative)
        for relative in _docs(entry).examples.values()
        if not (EXAMPLES_DIR / relative).exists()
    )
    assert not missing, f'{entry.view} declares missing example(s): {missing}'


@pytest.mark.parametrize('entry', VIEW_ENTRIES, ids=lambda e: e.view)
def test_every_declared_view_example_is_one_the_builder_looks_up(entry):
    # An example under a key nothing consumes is silently dropped.
    #
    # `_request_schema_and_example()` looks up `<method>_request`, either
    # plain or keyed by `(path, <method>_request)`. Anything else -- a
    # misspelled method, a response-example key borrowed from the resource
    # convention, a path this view does not serve -- is never read, so the
    # example never reaches the spec.
    docs = _docs(entry)
    consumable = set()
    for path, method in operations_served(docs):
        consumable.add(example_key(method))
        consumable.add((path, example_key(method)))
    unused = sorted(
        str(key) for key in docs.examples if key not in consumable
    )
    assert not unused, (
        f'{entry.view} declares example key(s) nothing looks up: {unused}'
    )
