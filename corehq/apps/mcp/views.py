"""MCP (Model Context Protocol) server endpoint.

Serves a stateless MCP endpoint over streamable HTTP (JSON-RPC 2.0 via
POST), authenticated with HQ-issued OAuth 2.0 bearer tokens. Discovery for
MCP clients is provided by the RFC 9728 protected-resource metadata
document, which points at HQ as the OAuth authorization server.
"""
import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from oauth2_provider.oauth2_backends import get_oauthlib_core

from corehq.apps.mcp.tools import TOOLS, ToolContext, ToolError
from corehq.apps.users.models import CouchUser

REQUIRED_SCOPES = ['access_apis']
MCP_PROTOCOL_VERSION = '2025-06-18'
SERVER_INFO = {'name': 'commcare-hq', 'version': '1.0'}


def _resource_metadata_url(request):
    return request.build_absolute_uri('/.well-known/oauth-protected-resource/mcp')


@require_GET
def oauth_protected_resource_metadata(request):
    return JsonResponse({
        'resource': request.build_absolute_uri('/mcp'),
        'authorization_servers': [request.build_absolute_uri('/').rstrip('/')],
        'bearer_methods_supported': ['header'],
        'scopes_supported': REQUIRED_SCOPES,
        'resource_name': 'CommCare HQ MCP server',
    })


def _unauthorized(request):
    response = JsonResponse({'error': 'invalid_token'}, status=401)
    response['WWW-Authenticate'] = (
        f'Bearer resource_metadata="{_resource_metadata_url(request)}"'
    )
    return response


def _rpc_result(req_id, result):
    return JsonResponse({'jsonrpc': '2.0', 'id': req_id, 'result': result})


def _rpc_error(req_id, code, message, status=200):
    return JsonResponse(
        {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': code, 'message': message}},
        status=status,
    )


@csrf_exempt
def mcp_endpoint(request):
    if request.method != 'POST':
        # Stateless server: no SSE stream, so GET is not supported
        return HttpResponse(status=405)
    valid, oauth_request = get_oauthlib_core().verify_request(
        request, scopes=REQUIRED_SCOPES)
    if not valid:
        return _unauthorized(request)
    # OAuth-authenticated requests must not grant superusers global admin
    # powers; CouchUser.is_global_admin checks this flag via the request.
    request.user = oauth_request.user
    request._auth_method_restricts_superuser_access = True

    try:
        message = json.loads(request.body)
    except ValueError:
        return _rpc_error(None, -32700, 'Parse error', status=400)
    if message.get('id') is None:
        # JSON-RPC notification (e.g. notifications/initialized): no response body
        return HttpResponse(status=202)
    context = ToolContext(
        couch_user=CouchUser.from_django_user(request.user),
        authorization=request.META.get('HTTP_AUTHORIZATION', ''),
    )
    return _dispatch(message, context)


def _tool_result(req_id, payload, is_error=False):
    return _rpc_result(req_id, {
        'content': [{'type': 'text', 'text': json.dumps(payload, default=str)}],
        'isError': is_error,
    })


def _dispatch(message, context):
    req_id = message['id']
    params = message.get('params') or {}
    if message.get('method') == 'initialize':
        return _rpc_result(req_id, {
            'protocolVersion': params.get('protocolVersion') or MCP_PROTOCOL_VERSION,
            'capabilities': {'tools': {}},
            'serverInfo': SERVER_INFO,
        })
    if message.get('method') == 'tools/list':
        return _rpc_result(req_id, {
            'tools': [tool.spec() for tool in TOOLS.values()],
        })
    if message.get('method') == 'tools/call':
        tool = TOOLS.get(params.get('name'))
        if tool is None:
            return _rpc_error(req_id, -32602, f"Unknown tool: {params.get('name')}")
        try:
            result = tool.handler(context, params.get('arguments') or {})
        except ToolError as err:
            return _tool_result(req_id, {'error': str(err)}, is_error=True)
        return _tool_result(req_id, result)
    return _rpc_error(req_id, -32601, f"Method not found: {message.get('method')}")
