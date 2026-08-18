"""Documentation declarations for function-based API views.

Tastypie resources declare documentation through a ``Docs`` inner class. The
hand-written API views use this decorator instead, which carries the same
information plus the paths the view serves.
"""

import functools
from dataclasses import dataclass, field

VIEW_DOCS = []


@dataclass
class ApiViewDocs:
    summary: str
    description: str
    paths: list
    doc_slug: str
    methods: list = field(default_factory=lambda: ['get'])
    parameters: list = field(default_factory=list)
    request_schemas: dict = field(default_factory=dict)
    response_schemas: dict = field(default_factory=dict)
    examples: dict = field(default_factory=dict)


def api_docs(**kwargs):
    """Attach OpenAPI documentation to a function-based API view."""
    docs = ApiViewDocs(**kwargs)

    def decorate(view):
        VIEW_DOCS.append(docs)

        @functools.wraps(view)
        def wrapper(*args, **view_kwargs):
            return view(*args, **view_kwargs)

        wrapper._openapi_docs = docs
        return wrapper

    return decorate
