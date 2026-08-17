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


def _require_member_of(couch_user, domain):
    if not domain or not couch_user.is_member_of(domain):
        raise ToolError(f"You are not a member of domain '{domain}'")


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


def list_lookup_tables(context, arguments):
    domain = arguments.get('domain')
    _require_member_of(context.couch_user, domain)
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
