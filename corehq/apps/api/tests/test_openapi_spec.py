"""Structural tests for the OpenAPI specification in docs/api/openapi/."""
import os
import re
from collections.abc import Iterator

import yaml
from django.conf import settings
from django.urls import Resolver404, resolve
from unmagic import fixture, use

OPERATION_ID_RE = re.compile(r'[a-z][a-zA-Z0-9]*')

#: The view each spec path served by a hand-written Django view must resolve to.
#:
#: Tastypie-served paths are deliberately absent. ``HqBaseResource
#: .get_urlpattern`` bakes ``resource_name`` into the URL pattern as a regex
#: literal, so asserting which resource answers ``/api/group/v1/`` only restates
#: the pattern the spec path was copied from -- a tautology.
#:
#: These paths do not have that property: they are independent, hand-ordered
#: entries in their apps' urlconfs, and several overlap. ``/a/{domain}/receiver/
#: api/`` and ``/a/{domain}/receiver/{app_id}/`` are the clearest case -- if the
#: two were ever reordered, the first would be shadowed by the second with
#: ``app_id='api'``, silently routing OpenRosa submissions to the wrong view
#: while ``test_all_paths_resolve`` still passed.
NON_TASTYPIE_VIEWS = {
    '/a/{domain}/api/case/v2/':
        'corehq.apps.hqcase.views.case_api',
    '/a/{domain}/api/case/v2/{case_id}':
        'corehq.apps.hqcase.views.case_api',
    '/a/{domain}/api/case/v2/ext/{external_id}/':
        'corehq.apps.hqcase.views.case_api',
    '/a/{domain}/api/case/v2/bulk-fetch/':
        'corehq.apps.hqcase.views.case_api_bulk_fetch',
    '/a/{domain}/api/form_attachment/v1/{instance_id}/{attachment_id}':
        'corehq.apps.api.object_fetch_api.view_form_attachment',
    '/a/{domain}/receiver/api/':
        'corehq.apps.receiverwrapper.views.post_api',
    '/a/{domain}/receiver/{app_id}/':
        'corehq.apps.receiverwrapper.views.post',
    '/a/{domain}/fixtures/fixapi/':
        'corehq.apps.fixtures.views.upload_fixture_api',
    '/a/{domain}/fixtures/fixapi/status/{download_id}/':
        'corehq.apps.fixtures.views.fixture_api_upload_status',
    '/a/{domain}/apps/api/import_app/':
        'corehq.apps.app_manager.views.app_import_api.import_app_api',
    '/a/{domain}/apps/api/{app_id}/multimedia/':
        'corehq.apps.app_manager.views.app_import_api.upload_multimedia_api',
    '/a/{domain}/apps/api/{app_id}/multimedia/status/{processing_id}/':
        'corehq.apps.app_manager.views.app_import_api.multimedia_status_api',
    '/a/{domain}/importer/excel/bulk_upload_api/':
        'corehq.apps.case_importer.views.bulk_case_upload_api',
    '/a/{domain}/api/messaging-event/v1/':
        'corehq.apps.api.resources.messaging_event.view.messaging_events',
    '/a/{domain}/api/messaging-event/v1/{event_id}/':
        'corehq.apps.api.resources.messaging_event.view.messaging_events',
}

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


@use(spec)
def test_every_operation_declares_401_and_403():
    """Standard error-response coverage every resource task must match."""
    for path, method, operation in _iter_operations(spec()):
        where = f'{method.upper()} {path}'
        responses = operation.get('responses', {})
        assert '401' in responses, f'{where} has no 401 response'
        assert '403' in responses, f'{where} has no 403 response'


@use(spec)
def test_operation_ids_are_lower_camel_case():
    for path, method, operation in _iter_operations(spec()):
        operation_id = operation['operationId']
        assert OPERATION_ID_RE.fullmatch(operation_id), (
            f'operationId {operation_id!r} on {method.upper()} {path} is not '
            'lowerCamelCase'
        )


def _concrete_url(path, path_item):
    """Substitute each path parameter's ``example`` to build a resolvable URL."""
    examples = {}
    parameters = list(path_item.get('parameters', []))
    for method, operation in path_item.items():
        if method in HTTP_METHODS:
            parameters.extend(operation.get('parameters', []))
    for parameter in parameters:
        if parameter.get('in') == 'path':
            examples[parameter['name']] = str(parameter['example'])
    try:
        return path.format(**examples)
    except KeyError as missing:
        raise AssertionError(
            f'{path} has a placeholder {missing} with no matching path '
            f'parameter declared; declared parameters: {sorted(examples)}'
        ) from None


def _view_name(func):
    return f'{func.__module__}.{func.__qualname__}'


@use(spec)
def test_non_tastypie_paths_resolve_to_the_expected_view():
    """Guard the hand-written Django paths against urlconf reordering.

    ``test_all_paths_resolve`` only checks that *something* answers each path.
    That is enough for the tastypie paths, whose URL patterns are generated from
    the resource name, but not for the paths below, where two patterns can match
    the same URL and only their order in the urlconf decides which one wins.
    """
    resolved = {
        path: _view_name(resolve(_concrete_url(path, path_item)).func)
        for path, path_item in spec()['paths'].items()
    }

    unknown = sorted(set(NON_TASTYPIE_VIEWS) - set(resolved))
    assert not unknown, (
        'NON_TASTYPIE_VIEWS names paths that are not in the spec:\n  '
        + '\n  '.join(unknown)
    )

    unlisted = sorted(
        path for path, view in resolved.items()
        if path not in NON_TASTYPIE_VIEWS and not view.startswith('tastypie.')
    )
    assert not unlisted, (
        'spec paths served by a hand-written view with no entry in '
        'NON_TASTYPIE_VIEWS:\n  ' + '\n  '.join(unlisted)
    )

    wrong = [
        f'{path} resolves to {resolved[path]}, expected {expected}'
        for path, expected in sorted(NON_TASTYPIE_VIEWS.items())
        if resolved[path] != expected
    ]
    assert not wrong, (
        'spec paths resolving to the wrong view:\n  ' + '\n  '.join(wrong)
    )


@use(spec)
def test_all_paths_resolve():
    """Every path in the spec must map to a real Django URL pattern."""
    unresolvable = []
    for path, path_item in spec()['paths'].items():
        url = _concrete_url(path, path_item)
        try:
            resolve(url)
        except Resolver404:
            unresolvable.append(f'{path} (tried {url})')
    assert not unresolvable, (
        'spec paths that do not resolve against Django URLconf:\n  '
        + '\n  '.join(unresolvable)
    )
