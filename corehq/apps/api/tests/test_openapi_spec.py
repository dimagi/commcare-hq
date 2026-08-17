"""Structural tests for the OpenAPI specification in docs/api/openapi/."""
import os
from collections.abc import Iterator

import yaml
from django.conf import settings
from unmagic import fixture, use

SPEC_ROOT = os.path.join(settings.FILEPATH, 'docs', 'api', 'openapi')
SPEC_PATH = os.path.join(SPEC_ROOT, 'openapi.yaml')
HTTP_METHODS = frozenset(
    ['get', 'put', 'post', 'delete', 'patch', 'head', 'options', 'trace']
)


def _resolve_refs(node, base_dir, document):
    """Recursively inline every ``$ref`` so the spec can be inspected as one dict.

    Handles relative file refs (``./components/schemas/group.yaml#/Group``) and
    fragment-only refs (``#/Group``). A fragment-only ref resolves against the
    document that contains it, not against the spec root. Per OpenAPI 3.0, keys
    alongside a ``$ref`` are ignored.

    Cycles are not expected in this spec; a cyclic ``$ref`` raises
    RecursionError, which is an acceptable failure mode for a test.
    """
    if isinstance(node, list):
        return [_resolve_refs(item, base_dir, document) for item in node]
    if not isinstance(node, dict):
        return node
    if '$ref' in node:
        file_part, _, fragment = node['$ref'].partition('#')
        if file_part:
            target_path = os.path.normpath(os.path.join(base_dir, file_part))
            with open(target_path) as f:
                next_document = yaml.safe_load(f)
            next_base = os.path.dirname(target_path)
        else:
            next_document = document
            next_base = base_dir
        resolved = next_document
        for key in [part for part in fragment.split('/') if part]:
            resolved = resolved[key]
        return _resolve_refs(resolved, next_base, next_document)
    return {
        key: _resolve_refs(value, base_dir, document)
        for key, value in node.items()
    }


def _load_spec():
    with open(SPEC_PATH) as f:
        document = yaml.safe_load(f)
    return _resolve_refs(document, SPEC_ROOT, document)


def _iter_operations(spec) -> Iterator[tuple[str, str, dict]]:
    for path, path_item in spec['paths'].items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                yield path, method, operation


@fixture(scope='module')
def spec():
    yield _load_spec()


@use(spec)
def test_spec_parses_and_refs_resolve():
    spec_ = spec()
    assert spec_['openapi'] == '3.0.3'
    assert spec_['paths'], 'spec declares no paths'


@use(spec)
def test_operation_ids_are_unique():
    seen = {}
    for path, method, operation in _iter_operations(spec()):
        operation_id = operation['operationId']
        assert operation_id not in seen, (
            f'duplicate operationId {operation_id!r}: '
            f'{seen[operation_id]} and {method.upper()} {path}'
        )
        seen[operation_id] = f'{method.upper()} {path}'


@use(spec)
def test_every_operation_has_agent_facing_fields():
    spec_ = spec()
    known_tags = {tag['name'] for tag in spec_['tags']}
    for path, method, operation in _iter_operations(spec_):
        where = f'{method.upper()} {path}'
        assert operation.get('summary'), f'{where} has no summary'
        assert operation.get('tags'), f'{where} has no tags'
        assert operation.get('responses'), f'{where} has no responses'
        unknown = set(operation['tags']) - known_tags
        assert not unknown, f'{where} uses undeclared tags: {unknown}'


@use(spec)
def test_every_path_parameter_has_an_example():
    """Task 4's URL-resolution test builds real URLs from these examples."""
    for path, path_item in spec()['paths'].items():
        parameters = list(path_item.get('parameters', []))
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                parameters.extend(operation.get('parameters', []))
        for parameter in parameters:
            if parameter.get('in') == 'path':
                assert 'example' in parameter, (
                    f'path parameter {parameter["name"]!r} on {path} '
                    'has no example'
                )
