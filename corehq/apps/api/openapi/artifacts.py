"""Locations of, and readers for, the generated OpenAPI artifacts.

The specs under ``docs/api/spec/`` are generated and committed by
``./manage.py generate_openapi``. The Redoc pages under ``docs/api/dist/`` are
built by ``yarn openapi:docs`` during the asset build and are not committed.

Both are immutable for the lifetime of a deploy, so successful reads are
cached for the process lifetime. A miss is not cached: the build or the
generator can run after a request has already seen the artifact absent (e.g.
a developer runs ``yarn openapi:docs`` after hitting a 404), and Django's
autoreloader does not watch these output directories, so a cached miss would
never clear itself short of a process restart.
"""

import hashlib
import json
from functools import wraps
from pathlib import Path

from django.conf import settings

from corehq.apps.api.openapi.catalogue import documented_entries

SPEC_DIR = Path(settings.BASE_DIR) / 'docs' / 'api' / 'spec'
DIST_DIR = Path(settings.BASE_DIR) / 'docs' / 'api' / 'dist'

BUNDLE_SLUG = 'bundle'

REGENERATE_HINT = "Run './manage.py generate_openapi' to generate it."
BUILD_HINT = "Run 'yarn openapi:docs' to build it."


def spec_path(slug):
    return SPEC_DIR / f'{slug}.json'


def page_path(slug):
    return DIST_DIR / f'{slug}.html'


def documented_slugs():
    return {entry.doc_slug for entry in documented_entries()}


def cache_hits_only(func):
    """Like ``lru_cache``, but a ``None`` result is never memoised.

    Every function wrapped here treats ``None`` as "the artifact does not
    exist yet". Caching that outcome for the process lifetime would mean a
    build or generation step that runs after the first request could never
    be observed without a restart.
    """
    cache = {}

    @wraps(func)
    def wrapper(slug):
        if slug in cache:
            return cache[slug]
        result = func(slug)
        if result is not None:
            cache[slug] = result
        return result

    wrapper.cache_clear = cache.clear
    return wrapper


@cache_hits_only
def read_spec(slug):
    """The generated spec for ``slug``, or None if it has not been generated.

    The returned document is cached and shared by every caller in this
    process. Treat it as read-only: mutate it in place (e.g. to substitute
    a host into ``servers``) and every later reader -- for every request,
    for every host -- sees the corrupted document, since the cache is only
    cleared by a process restart. Callers that need to modify the document
    must ``copy.deepcopy`` it first.
    """
    path = spec_path(slug)
    if not path.exists():
        return None
    return json.loads(path.read_text())


@cache_hits_only
def read_page(slug):
    """The built Redoc page for ``slug``, or None if the build has not run."""
    path = page_path(slug)
    if not path.exists():
        return None
    return path.read_text()


@cache_hits_only
def spec_content_hash(slug):
    path = spec_path(slug)
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


_REF_PREFIX = '#/components/schemas/'


def _resolve(schema, spec, seen):
    """Follow a chain of local ``$ref``s to the schema they name.

    Returns ``(schema, seen)`` -- the refs followed come back with it, because
    a caller that recurses into ``anyOf`` branches must know what has already
    been followed or a self-referential document recurses forever.

    Returns an empty schema for a ref already in ``seen``, and for a remote
    or malformed ref, which this generator never produces.
    """
    while True:
        ref = schema.get('$ref')
        if ref is None:
            return schema, seen
        if ref in seen or not ref.startswith(_REF_PREFIX):
            return {}, seen
        seen = seen | {ref}
        schema = (
            spec.get('components', {})
            .get('schemas', {})
            .get(ref[len(_REF_PREFIX):], {})
        )


def _record_property_items(schema, spec, seen=frozenset()):
    """Yield ``(name, property)`` pairs for one record's fields.

    List responses are ``{meta, objects: [record]}``; detail responses are the
    record itself. A response may also be a ``$ref``, or branch through
    ``anyOf``/``oneOf``/``allOf`` -- ``case-v2``'s detail response does. Every
    branch contributes, and a name may be yielded more than once, so the caller
    must treat a field as described if any occurrence describes it.
    """
    schema, seen = _resolve(schema, spec, seen)
    for key in ('anyOf', 'oneOf', 'allOf'):
        if key in schema:
            for branch in schema[key]:
                yield from _record_property_items(branch, spec, seen)
            return
    properties = schema.get('properties', {})
    inner, _ = _resolve(
        properties.get('objects', {}).get('items', {}), spec, seen
    )
    envelope = inner.get('properties')
    yield from (properties if envelope is None else envelope).items()


def description_coverage(slug):
    """How many of ``slug``'s response properties carry a description.

    Returns ``(described, total)``. Each property name is counted once across
    every success response, so a field documented on one endpoint is not
    counted again on another.
    """
    spec = read_spec(slug)
    if spec is None:
        return (0, 0)
    described = {}
    for item in spec.get('paths', {}).values():
        for method, operation in item.items():
            if method == 'parameters':
                continue
            for status, response in operation.get('responses', {}).items():
                if not status.startswith('2'):
                    continue
                schema = (
                    response.get('content', {})
                    .get('application/json', {})
                    .get('schema')
                )
                if not schema:
                    continue
                for name, prop in _record_property_items(schema, spec):
                    if not isinstance(prop, dict):
                        continue
                    described[name] = (
                        described.get(name, False) or 'description' in prop
                    )
    return (sum(described.values()), len(described))
