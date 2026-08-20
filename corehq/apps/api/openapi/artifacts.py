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

This module locates and reads; it does not interpret. Questions about what a
spec *says* -- which response fields it publishes, how many carry a
description -- belong to ``response_fields``, which takes the document this
module returns and never touches the filesystem.
"""

import hashlib
import json
from functools import wraps
from pathlib import Path

from django.conf import settings

# Re-exported for docs_views, which reads the served-slug allowlist as
# artifacts.documented_slugs().
from corehq.apps.api.openapi.catalogue import documented_slugs  # noqa: F401

SPEC_DIR = Path(settings.BASE_DIR) / 'docs' / 'api' / 'spec'
DIST_DIR = Path(settings.BASE_DIR) / 'docs' / 'api' / 'dist'

BUNDLE_SLUG = 'bundle'

REGENERATE_HINT = "Run './manage.py generate_openapi' to generate it."
BUILD_HINT = "Run 'yarn openapi:docs' to build it."


def spec_path(slug):
    return SPEC_DIR / f'{slug}.json'


def page_path(slug):
    return DIST_DIR / f'{slug}.html'


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
