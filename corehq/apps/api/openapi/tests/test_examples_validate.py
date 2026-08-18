"""Every shipped example must validate against the schema it's attached to.

Without this, a schema and its example can be self-consistently wrong --
both silently agree with each other while disagreeing with what the API
actually does -- and a plain "are the example's keys a subset of the
schema's properties" check will not catch it (a subset check does not
verify ``required``, ``oneOf``/``anyOf`` branch membership, ``enum``
values, and so on).
"""

import pytest

from corehq.apps.api.openapi.builder import build_all
from corehq.apps.api.openapi.tests.oas_validation import validator_for


def _iter_examples(documents):
    """Yield (spec, path, method, kind, schema, example) for every example
    attached to a request body or a response in the generated documents.
    """
    for spec, document in documents.items():
        for path, item in document.get('paths', {}).items():
            for method, operation in item.items():
                if method == 'parameters':
                    continue
                request_body = operation.get('requestBody')
                if request_body:
                    body = request_body.get('content', {}).get(
                        'application/json', {}
                    )
                    if 'example' in body and 'schema' in body:
                        yield (
                            spec,
                            path,
                            method,
                            'requestBody',
                            body['schema'],
                            body['example'],
                            document,
                        )
                for status, response in operation.get('responses', {}).items():
                    body = response.get('content', {}).get(
                        'application/json', {}
                    )
                    if 'example' in body and 'schema' in body:
                        yield (
                            spec,
                            path,
                            method,
                            f'response {status}',
                            body['schema'],
                            body['example'],
                            document,
                        )


def _examples():
    documents = build_all()
    return list(_iter_examples(documents))


@pytest.mark.parametrize(
    'spec, path, method, kind, schema, example, document',
    _examples(),
    ids=[
        f'{spec}:{path}:{method}:{kind}'
        for spec, path, method, kind, *_ in _examples()
    ],
)
def test_example_validates_against_its_own_schema(
    spec,
    path,
    method,
    kind,
    schema,
    example,
    document,
):
    validator = validator_for(document, schema)
    errors = list(validator.iter_errors(example))
    assert not errors, (
        f'{spec} {method.upper()} {path} ({kind}): example does not '
        f'match its own schema: {"; ".join(e.message for e in errors)}'
    )


def test_at_least_one_example_is_covered():
    # A sanity check that this test file's parametrization isn't
    # silently empty (e.g. because build_all() stopped producing
    # examples) -- a test with zero cases "passes" without checking
    # anything.
    assert len(_examples()) >= 5
