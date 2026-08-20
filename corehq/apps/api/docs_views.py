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
from django.http import HttpResponse
from django.shortcuts import render

from corehq.apps.api.cors import add_cors_headers_to_response
from corehq.apps.api.openapi import artifacts
from corehq.apps.api.openapi.catalogue import documented_entries

logger = logging.getLogger(__name__)


def with_host(spec, host):
    """A copy of ``spec`` whose ``servers`` host default is ``host``.

    The generated specs declare ``https://{host}`` with a default of
    www.commcarehq.org. Serving that unchanged from another deployment would
    point a client that follows the default at the wrong installation.

    Copies rather than mutates: ``artifacts.read_spec`` caches its result for
    the process lifetime, so mutating it would poison every later request.

    Reflecting ``host`` back unvalidated is safe only because Django's
    ``ALLOWED_HOSTS`` check rejects a request with an unlisted ``Host``
    header before this view ever runs, in any environment where it is set
    to a real whitelist (i.e. production).
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
    payload = json.dumps(with_host(spec, host), indent=2, sort_keys=True)
    response = HttpResponse(payload, content_type='application/json')
    add_cors_headers_to_response(response)
    digest = hashlib.sha256(
        f'{artifacts.spec_content_hash(slug)}:{host}'.encode()
    ).hexdigest()
    # Currently inert: nothing answers If-None-Match (no
    # ConditionalGetMiddleware), and NoCacheMiddleware marks this response
    # no-store, so no client or proxy may act on it. Kept anyway because it
    # is correct and cheap to compute, in case that ever changes.
    response['ETag'] = f'"{digest}"'
    return response


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
    """Lists the documented APIs, and how completely each is described."""
    apis = []
    for entry in documented_entries():
        described, total = artifacts.description_coverage(entry.doc_slug)
        apis.append(
            {
                'slug': entry.doc_slug,
                'title': (artifacts.read_spec(entry.doc_slug) or {})
                .get('info', {})
                .get('title', entry.doc_slug),
                'described': described,
                'total': total,
                'complete': bool(total) and described == total,
            }
        )
    apis.sort(key=lambda api: api['title'])
    return render(request, 'api/docs_index.html', {'apis': apis})
