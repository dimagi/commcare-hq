"""The response-field walk, exercised against documents rather than files.

These cases moved out of ``test_artifacts.py`` when the walk moved out of
``artifacts.py``. Each one used to write its document to a temporary
directory, monkeypatch ``SPEC_DIR`` and clear ``read_spec``'s cache around
it -- five lines of file plumbing per assertion, all of it there only
because the function under test took a slug and went to disk for it.

Nothing here reads a file. The cases that check a *committed* spec's
coverage stayed in ``test_artifacts.py``, where composing the reader with
the analyser is the point.
"""

from corehq.apps.api.openapi import response_fields


def _spec(schema, components=None):
    """A minimal document publishing ``schema`` as one GET's 200 response."""
    document = {
        'openapi': '3.0.3',
        'paths': {
            '/thing/': {
                'get': {
                    'responses': {
                        '200': {
                            'content': {'application/json': {
                                'schema': schema,
                            }},
                        },
                    },
                },
            },
        },
    }
    if components:
        document['components'] = {'schemas': components}
    return document


def test_coverage_is_zero_for_an_empty_document():
    assert response_fields.description_coverage({}) == (0, 0)
    assert response_fields.undescribed_fields({}) == []


def test_coverage_counts_fields_across_anyof_branches():
    spec = _spec({'anyOf': [
        {'type': 'object', 'properties': {
            'described': {'type': 'string', 'description': 'yes'},
            'bare': {'type': 'string'},
        }},
        {'type': 'object', 'properties': {'other': {'type': 'string'}}},
    ]})
    assert response_fields.description_coverage(spec) == (1, 3)


def test_coverage_descends_into_a_cases_list_envelope():
    # A function-based view's list response wraps its records in ``cases``
    # (not the Tastypie ``objects``), and each item is an anyOf of a record
    # or an error stub. Coverage must count the record's fields, not the
    # envelope's ``matching_records``/``next`` bookkeeping.
    record_or_error = {'anyOf': [
        {'type': 'object', 'properties': {
            'case_name': {'type': 'string', 'description': 'the name'},
            'owner_id': {'type': 'string'},
        }},
        {'type': 'object', 'properties': {'error': {'type': 'string'}}},
    ]}
    spec = _spec({
        'type': 'object',
        'properties': {
            'matching_records': {'type': 'integer'},
            'cases': {'type': 'array', 'items': record_or_error},
            'next': {'type': 'object'},
        },
    })
    # case_name (described), owner_id and error (bare); the envelope's
    # matching_records and next are not counted.
    assert response_fields.description_coverage(spec) == (1, 3)


def test_coverage_follows_a_ref_response_schema():
    spec = _spec(
        {'$ref': '#/components/schemas/Thing'},
        {'Thing': {
            'type': 'object',
            'properties': {
                'named': {'type': 'string', 'description': 'documented'},
                'plain': {'type': 'string'},
            },
        }},
    )
    assert response_fields.description_coverage(spec) == (1, 2)


def test_coverage_survives_a_self_referential_ref():
    spec = _spec(
        {'$ref': '#/components/schemas/Loop'},
        {'Loop': {'allOf': [{'$ref': '#/components/schemas/Loop'}]}},
    )
    assert response_fields.description_coverage(spec) == (0, 0)


def test_a_field_described_on_one_branch_stays_described():
    """The branch merge must not let a bare occurrence of a name overwrite a
    described one -- the ordering of anyOf branches is not meaningful."""
    spec = _spec({'anyOf': [
        {'properties': {'x': {'description': 'documented'}}},
        {'properties': {'x': {}}},
    ]})
    assert response_fields.description_coverage(spec) == (1, 1)


def test_undescribed_fields_reports_each_occurrence_separately():
    """Where ``description_coverage`` merges a name across endpoints, this
    reports the endpoint that publishes it bare -- the reference page
    renders each operation's schema on its own."""
    spec = _spec({'properties': {
        'described': {'description': 'yes'},
        'bare': {},
    }})
    spec['paths']['/other/'] = {'get': {'responses': {'200': {
        'content': {'application/json': {'schema': {'properties': {
            'bare': {'description': 'documented over here'},
        }}}},
    }}}}
    assert response_fields.description_coverage(spec) == (2, 2)
    assert response_fields.undescribed_fields(spec) == [
        ('/thing/', 'get', 'bare')
    ]
