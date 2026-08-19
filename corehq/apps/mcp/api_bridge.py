"""In-process bridge from MCP tools to HQ's domain REST APIs.

Requests are dispatched to the resolved API view inside the current
process, carrying the MCP caller's own Authorization header. The API
stack therefore performs its usual authentication, permission, and
throttling checks — the bridge grants nothing a caller couldn't already
do against the REST API directly.

Only paths under ``/a/<domain>/api/`` can be dispatched.
"""
import json
import re

from django.contrib.auth.models import AnonymousUser
from django.test.client import RequestFactory
from django.urls import Resolver404, resolve

from corehq.apps.mcp.tools import ToolError

ALLOWED_PATH_RE = re.compile(r'[\w.\-/]+')


def call_domain_api(authorization, domain, path, method='GET', params=None, body=None):
    full_path = _build_path(domain, path)
    request = _build_request(authorization, full_path, method, params, body)
    # Bridge requests bypass middleware; provide the attributes the API
    # stack expects middleware to have set. The API's own auth decorators
    # replace request.user after verifying the forwarded bearer token.
    request.user = AnonymousUser()
    request.domain = domain
    try:
        match = resolve(full_path)
    except Resolver404:
        raise ToolError(f"No API found at '{full_path}'. Use list_apis to see "
                        "available paths.")
    response = match.func(request, *match.args, **match.kwargs)
    return {
        'status': response.status_code,
        'body': _read_body(response),
    }


def _build_path(domain, path):
    path = (path or '').lstrip('/')
    if not ALLOWED_PATH_RE.fullmatch(path) or '..' in path:
        raise ToolError(f"Invalid API path: '{path}'")
    return f'/a/{domain}/api/{path}'


def _build_request(authorization, full_path, method, params, body):
    factory = RequestFactory()
    if method == 'GET':
        return factory.get(full_path, data=params or {},
                           HTTP_AUTHORIZATION=authorization)
    return factory.generic(
        method, full_path,
        data=json.dumps(body or {}),
        content_type='application/json',
        HTTP_AUTHORIZATION=authorization,
    )


def _read_body(response):
    content = getattr(response, 'content', b'').decode('utf-8', errors='replace')
    if 'application/json' in response.get('Content-Type', ''):
        try:
            return json.loads(content)
        except ValueError:
            pass
    return content
