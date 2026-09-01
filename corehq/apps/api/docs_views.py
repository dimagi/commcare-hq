"""Views publishing the generated OpenAPI specs and their reference pages.

These views are deliberately unauthenticated. They serve endpoint descriptions
that carry no credentials, and the same content is already published, so gating
them would only make the reference harder for integrators to reach.
"""

import copy
import hashlib
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotModified
from django.shortcuts import render

from corehq.apps.api.cors import add_cors_headers_to_response
from corehq.apps.api.openapi import artifacts, response_fields

logger = logging.getLogger(__name__)

#: How long a served spec stays fresh in a client or shared cache.
#:
#: These replace public reference documentation, so they are worth caching:
#: ``bundle.json`` alone is over 400 KB, and by default
#: ``NoCacheMiddleware`` marks every response ``no-store``, so each visit
#: re-transferred all of it.
#:
#: Short rather than deploy-length because the URLs are stable. A hashed
#: static asset can be cached forever precisely because a new build gets a
#: new URL; ``/api/openapi.json`` does not, so a long freshness window would
#: leave an integrator's browser showing a spec from an arbitrary earlier
#: deploy, with no way to invalidate it. Instead the window is short and
#: ``api_spec()`` answers ``If-None-Match``: a repeat visit within a deploy
#: costs a 304 with no body, and a deploy reaches everyone within one
#: window.
SPEC_CACHE_SECONDS = 300


def _allow_caching(response):
    """Let ``NoCacheMiddleware`` serve ``response`` from a cache.

    That middleware stamps ``no-store`` on everything unless a response
    opts out through this attribute, and it rewrites ``Content-Type`` from
    the URL path's extension when it does. Only the ``*.json`` spec routes
    opt in: their paths end in ``.json``, so the rewrite is a no-op, while
    the HTML reference pages route through extensionless URLs that
    ``mimetypes.guess_type()`` cannot name.
    """
    response._always_allow_browser_caching = True
    response._cache_max_age = str(SPEC_CACHE_SECONDS)
    return response


def with_host(spec, host):
    """A copy of ``spec`` whose ``servers`` host default is ``host``.

    The generated specs declare ``https://{host}`` with a default of
    www.commcarehq.org. Serving that unchanged from another deployment would
    point a client that follows the default at the wrong installation.

    Copies rather than mutates: ``artifacts.read_spec`` caches its result for
    the process lifetime, so mutating it would poison every later request.

    ``host`` comes from the request and is reflected without validation,
    so that one build of a spec is correct on every deployment -- India,
    the EU, a self-hosted instance -- without each needing its own
    configured hostname. What keeps that safe is Django's ``ALLOWED_HOSTS``
    check, which rejects an unlisted ``Host`` before this view runs.

    Note what that does *not* guarantee here: ``ALLOWED_HOSTS`` is not set
    in ``settings.py``, and every configuration in this repository
    (``dev_settings``, both docker settings files) sets it to ``['*']``.
    Production's value comes from commcare-cloud, outside this repo, so the
    defence is real but unverifiable from here. The blast radius is small
    either way -- the reflected value lands in a ``servers`` default that a
    reader sees, and ``api_spec()`` keys its ETag on the host, so one
    host's document can never be cached and served for another.
    """
    servers = spec.get('servers')
    if not servers:
        return spec
    substituted = []
    for server in servers:
        server = copy.deepcopy(server)
        variables = server.get('variables', {})
        if 'host' in variables:
            variables['host'] = {**variables['host'], 'default': host}
        substituted.append(server)
    return {**spec, 'servers': substituted}


def _not_found(message):
    """404 with an explanatory body in development only."""
    body = message if settings.DEBUG else ''
    return HttpResponse(body, status=404, content_type='text/plain')


def api_spec(request, slug=None):
    slug = slug or artifacts.BUNDLE_SLUG
    if (
        slug != artifacts.BUNDLE_SLUG
        and slug not in artifacts.documented_slugs()
    ):
        return _not_found(f'No OpenAPI spec for {slug!r}.')
    spec = artifacts.read_spec(slug)
    if spec is None:
        logger.warning(
            'OpenAPI spec %r is missing from %s', slug, artifacts.SPEC_DIR
        )
        return _not_found(
            f'{artifacts.spec_path(slug)} is missing. '
            f'{artifacts.REGENERATE_HINT}'
        )
    host = request.get_host()
    # Keyed on the spec's content and the host substituted into it: the two
    # things that decide the bytes below. It is answered here rather than by
    # ConditionalGetMiddleware, which this project does not install.
    digest = hashlib.sha256(
        f'{artifacts.spec_content_hash(slug)}:{host}'.encode()
    ).hexdigest()
    etag = f'"{digest}"'
    if _matches_client_etag(request, etag):
        # A 304 must still carry the caching headers, or the client is being
        # told to discard the copy it just offered.
        return _allow_caching(HttpResponseNotModified(headers={'ETag': etag}))

    payload = json.dumps(with_host(spec, host), indent=2, sort_keys=True)
    response = HttpResponse(payload, content_type='application/json')
    add_cors_headers_to_response(response)
    response['ETag'] = etag
    return _allow_caching(response)


def _matches_client_etag(request, etag):
    """Whether ``If-None-Match`` offers a copy identical to ``etag``.

    ``*`` matches any existing representation. ``If-None-Match`` uses weak
    comparison, so a ``W/`` prefix is ignored -- nothing here emits weak
    tags, but a proxy may relay one back.
    """
    header = request.headers.get('If-None-Match')
    if not header:
        return False
    offered = {
        tag[2:] if tag.startswith('W/') else tag
        for tag in (raw.strip() for raw in header.split(','))
        if tag
    }
    return '*' in offered or etag in offered


def api_docs_page(request, slug):
    """The generated Redoc reference page for one API.

    The page is produced by ``yarn openapi:docs`` during the asset build and
    is not committed. Deployed environments always build static assets, so
    a missing page means either a local checkout that has not run the build
    or a broken deploy -- hence the warning log as well as the 404.
    """
    if slug not in artifacts.documented_slugs():
        return _not_found(f'No API documentation for {slug!r}.')
    page = artifacts.read_page(slug)
    if page is None:
        logger.warning(
            'API reference page %r is missing from %s',
            slug,
            artifacts.DIST_DIR,
        )
        return _not_found(
            f'{artifacts.page_path(slug)} has not been built. '
            f'{artifacts.BUILD_HINT}'
        )
    return HttpResponse(page)


def api_docs_index(request):
    """Lists the documented APIs, and how completely each is described.

    Covers every slug the generator produces a spec for -- the catalogue's
    resources and the function-based views (Case API v2) alike -- so an API
    whose spec and reference page are built and served does not go unlisted.

    The coverage figures are recomputed per request rather than cached,
    which looks worth optimising and measurably is not: walking all twenty
    specs takes about 0.1 ms, because ``read_spec()`` already caches the
    parsed documents and only the traversal repeats. Caching the numbers
    would add an invalidation problem to save a tenth of a millisecond.
    """
    apis = []
    for slug in artifacts.documented_slugs():
        spec = artifacts.read_spec(slug) or {}
        described, total = response_fields.description_coverage(spec)
        apis.append(
            {
                'slug': slug,
                'title': spec.get('info', {}).get('title', slug),
                'described': described,
                'total': total,
                'complete': bool(total) and described == total,
            }
        )
    apis.sort(key=lambda api: api['title'])
    return render(request, 'api/docs_index.html', {'apis': apis})
