"""The guards resource entries get, applied to view entries.

``test_documented_fields.py`` checks that a documented *resource* declares
prose, that its examples resolve, and that its published fields carry
descriptions. Those checks all iterate ``documented_entries()``, so a
function-based view catalogued in ``VIEW_CATALOGUE`` had none of them: it
could ship an empty summary, or an example key nothing looks up, and only
a human reading the rendered page would notice.

The response-description guard arrives with case v2's own field
descriptions, since it is what pins them.

The two resource guards with no counterpart here are deliberate.
``test_no_documented_write_method_is_a_phantom`` compares a spec against
tastypie's dispatch table, and ``..._files_its_field_docs_correctly``
validates a ``Docs`` class; a view has neither. Its routed-URL coverage
lives in ``test_case_v2_urls.py``, which needs the URLconf.
"""

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
    """An example under a key nothing consumes is silently dropped.

    ``_request_schema_and_example()`` looks up ``<method>_request``, either
    plain or keyed by ``(path, <method>_request)``. Anything else -- a
    misspelled method, a response-example key borrowed from the resource
    convention, a path this view does not serve -- is never read, so the
    example simply never reaches the spec and nothing says so.
    """
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
