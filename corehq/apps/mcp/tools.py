"""Registry of tools exposed by the CommCare HQ MCP server.

Each tool is a plain function taking ``(couch_user, arguments)`` and
returning a JSON-serializable dict. Tool errors that should be reported
to the calling model (rather than crash the request) are raised as
:class:`ToolError`.
"""
from dataclasses import dataclass

from corehq.apps.fixtures.models import LookupTable


class ToolError(Exception):
    """An error the calling model should see as a tool result."""


@dataclass(frozen=True)
class ToolContext:
    """What a tool handler knows about the calling request."""
    couch_user: object
    authorization: str  # the caller's Authorization header, for API forwarding
    # Domains a domain:<name>-scoped token is limited to; None = unrestricted
    token_domains: frozenset = None


def _require_domain_access(context, domain):
    if not domain or not context.couch_user.is_member_of(domain):
        raise ToolError(f"You are not a member of domain '{domain}'")
    if context.token_domains is not None and domain not in context.token_domains:
        raise ToolError(
            f"Your access token is not scoped to domain '{domain}'. "
            'Re-authorize with access to that project space.')


def whoami(context, arguments):
    return {
        'username': context.couch_user.username,
        'domains': context.couch_user.domains,
    }


def list_apis(context, arguments):
    # Imported here to avoid dragging the API urlconf in at import time
    from corehq.apps.api.urls import _OLD_API_LIST
    apis = []
    for version, resources in _OLD_API_LIST:
        if version != (0, 5):
            continue
        for resource_class in resources:
            meta = resource_class._meta
            apis.append({
                'name': meta.resource_name,
                'path': f'/a/{{domain}}/api/v0.5/{meta.resource_name}/',
                'list_methods': list(meta.list_allowed_methods),
                'detail_methods': list(meta.detail_allowed_methods),
            })
    return {'apis': apis}


def call_api_read(context, arguments):
    # Imported here: api_bridge imports ToolError from this module
    from corehq.apps.mcp.api_bridge import call_domain_api
    domain = arguments.get('domain')
    _require_domain_access(context, domain)
    return call_domain_api(
        context.authorization,
        domain,
        arguments.get('path'),
        params=arguments.get('query_params'),
    )


WRITE_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')


def call_api_write(context, arguments):
    # Imported here: api_bridge imports ToolError from this module
    from corehq.apps.mcp.api_bridge import call_domain_api
    domain = arguments.get('domain')
    _require_domain_access(context, domain)
    method = (arguments.get('method') or '').upper()
    if method not in WRITE_METHODS:
        raise ToolError(
            f"Method must be one of {', '.join(WRITE_METHODS)}; got '{method}'")
    return call_domain_api(
        context.authorization,
        domain,
        arguments.get('path'),
        method=method,
        body=arguments.get('body'),
    )


def list_lookup_tables(context, arguments):
    domain = arguments.get('domain')
    _require_domain_access(context, domain)
    return {
        'domain': domain,
        'lookup_tables': [
            {'id': str(table.id), 'tag': table.tag, 'is_global': table.is_global}
            for table in LookupTable.objects.by_domain(domain)
        ],
    }


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: callable

    def spec(self):
        return {
            'name': self.name,
            'description': self.description,
            'inputSchema': self.input_schema,
        }


TOOLS = {tool.name: tool for tool in [
    Tool(
        name='list_apis',
        description=(
            'List the REST API resources available on CommCare HQ: each '
            'entry gives the resource name, its URL path template, and the '
            'HTTP methods allowed on the list and detail endpoints. Use '
            'this to discover what call_api_read and call_api_write can do.'
        ),
        input_schema={
            'type': 'object',
            'properties': {},
            'additionalProperties': False,
        },
        handler=list_apis,
    ),
    Tool(
        name='call_api_read',
        description=(
            'Perform a read (GET) against a CommCare HQ REST API in a '
            'project space. path is relative to /a/{domain}/api/, e.g. '
            "'v0.5/case/' or 'v0.5/lookup_table/'. Discover available "
            'paths with list_apis. Returns the HTTP status and response '
            'body. The call runs with your own permissions.'
        ),
        input_schema={
            'type': 'object',
            'properties': {
                'domain': {'type': 'string', 'description': 'The project space name'},
                'path': {'type': 'string', 'description': "API path, e.g. 'v0.5/case/'"},
                'query_params': {
                    'type': 'object',
                    'description': 'Optional query string parameters',
                    'additionalProperties': {'type': 'string'},
                },
            },
            'required': ['domain', 'path'],
            'additionalProperties': False,
        },
        handler=call_api_read,
    ),
    Tool(
        name='call_api_write',
        description=(
            'Perform a write (POST, PUT, PATCH or DELETE) against a '
            'CommCare HQ REST API in a project space, with a JSON body. '
            'path is relative to /a/{domain}/api/. Discover available '
            'paths and allowed methods with list_apis. This modifies real '
            'project data and runs with your own permissions - be sure '
            'the user wants the change before calling it.'
        ),
        input_schema={
            'type': 'object',
            'properties': {
                'domain': {'type': 'string', 'description': 'The project space name'},
                'path': {'type': 'string', 'description': "API path, e.g. 'v0.5/lookup_table/'"},
                'method': {'type': 'string', 'enum': list(WRITE_METHODS)},
                'body': {'type': 'object', 'description': 'JSON request body'},
            },
            'required': ['domain', 'path', 'method'],
            'additionalProperties': False,
        },
        handler=call_api_write,
    ),
    Tool(
        name='whoami',
        description=(
            "Get the authenticated CommCare HQ user's username and the "
            "project spaces (domains) they belong to. Call this first to "
            "discover which domains other tools can be used with."
        ),
        input_schema={
            'type': 'object',
            'properties': {},
            'additionalProperties': False,
        },
        handler=whoami,
    ),
    Tool(
        name='list_lookup_tables',
        description=(
            'List the lookup tables (fixtures) in a CommCare HQ project '
            'space. Use a domain from whoami.'
        ),
        input_schema={
            'type': 'object',
            'properties': {
                'domain': {
                    'type': 'string',
                    'description': 'The project space name',
                },
            },
            'required': ['domain'],
            'additionalProperties': False,
        },
        handler=list_lookup_tables,
    ),
]}
