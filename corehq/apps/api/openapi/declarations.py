"""Helpers for writing the in-code API documentation.

A resource declares documentation through a ``Docs`` inner class, and a
function-based view through the ``@api_docs`` decorator. Both spell their
query parameters as OpenAPI parameter objects, which are mostly boilerplate:
every one of them is ``in: query`` and optional, and differs only in its name,
its description and its schema. Writing that out by hand repeated the same
five keys dozens of times and made a mistyped key look like an ordinary line.
"""

#: Every documented resource exposes ``resource_uri`` and describes it the
#: same way. Declared once so the wording cannot drift between resources.
RESOURCE_URI_DESCRIPTION = 'URI of this record in the API.'

#: Schema fragments merged into a declared field before the resource's own
#: ``Docs.field_schemas`` entry, for fields tastypie generates rather than
#: the resource author writing them.
#:
#: ``resource_uri`` is the only such field. It has no ``help_text`` to hang a
#: description on, and every resource that has one means the same thing by
#: it, so describing it here rather than in each ``Docs`` keeps nine
#: identical declarations out of the resources -- and keeps a resource that
#: simply forgot to write one from shipping an undescribed field.
DEFAULT_FIELD_SCHEMAS = {
    'resource_uri': {'description': RESOURCE_URI_DESCRIPTION},
}


def response_object(description, schema=None):
    """One OpenAPI Response Object: prose, plus a JSON body if there is one.

    Named for the construct it builds rather than ``json_response``, which
    is already a widely used (and deprecated) Django helper in this
    codebase -- ``dimagi.utils.web.json_response`` -- and would read as
    that one at these call sites.

    ``schema`` of ``None`` means a response with no body at all -- a
    write whose resource does not return the record. That is a different
    statement from a body whose schema happens to be empty, so the test
    is ``is None`` rather than falsiness.
    """
    response = {'description': description}
    if schema is not None:
        response['content'] = {'application/json': {'schema': schema}}
    return response


def query_parameter(name, description=None, schema=None):
    """One optional query parameter, as an OpenAPI parameter object.

    The single spelling of a query parameter for this project: the
    resources' ``Docs.parameters``, the parameters derived from a
    resource's ``Meta.filtering`` and pagination settings, and the case
    API's filter parameters all come through here.

    ``schema`` defaults to a plain string, which is what all but a handful
    of CommCare's query parameters are. Pass a full JSON Schema fragment for
    the rest -- ``{'type': 'string', 'format': 'date-time'}`` for a date, or
    ``{'type': 'integer', 'default': 20}`` for a paging limit.

    ``description`` is omitted rather than set empty when there is none: an
    empty description renders as one in the reference pages, and the
    parameters derived from ``Meta.filtering`` genuinely have none -- the
    filter's own name is all tastypie tells us about it.

    There is deliberately no ``required`` argument: a required query
    parameter would be a filter a client cannot omit, and CommCare has none.
    A future one should be declared as a literal, so it reads as the
    exception it is.
    """
    parameter = {
        'name': name,
        'in': 'query',
        'required': False,
    }
    if description:
        parameter['description'] = description
    parameter['schema'] = schema if schema is not None else {'type': 'string'}
    return parameter
