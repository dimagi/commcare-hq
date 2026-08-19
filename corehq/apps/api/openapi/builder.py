"""Assembly of complete OpenAPI documents for the CommCare data APIs."""

from corehq.apps.api.openapi.catalogue import (
    documented_entries,
    documented_view_entries,
)
from corehq.apps.api.openapi.docs import collect_docs
from corehq.apps.api.openapi.operations import resource_paths
from corehq.apps.api.openapi.security import (
    SECURITY_REQUIREMENT,
    SECURITY_SCHEMES,
)
from corehq.apps.api.openapi.view_operations import view_paths

OPENAPI_VERSION = '3.0.3'

SERVERS = [
    {
        'url': 'https://{host}',
        'description': 'A CommCare HQ instance.',
        'variables': {
            'host': {
                'default': 'www.commcarehq.org',
                'description': 'Hostname of the CommCare HQ instance.',
            },
        },
    }
]

PAGINATION_META_SCHEMA = {
    'type': 'object',
    'description': 'Pagination metadata for a page of records.',
    'properties': {
        'limit': {'type': 'integer'},
        'offset': {'type': 'integer'},
        'total_count': {'type': 'integer'},
        'next': {'type': 'string', 'nullable': True},
        'previous': {'type': 'string', 'nullable': True},
    },
}


#: Every schema this generator can publish under ``components.schemas``,
#: keyed by the name a ``$ref`` addresses it as. A document carries the
#: entries it actually references and no others, so adding one here is
#: enough -- there is no second place to register it.
COMPONENT_SCHEMAS = {
    'PaginationMeta': PAGINATION_META_SCHEMA,
}

_REF_PREFIX = '#/components/schemas/'


def _referenced_components(node):
    """The component names ``node`` reaches through ``$ref``.

    A structural walk rather than a search for the reference string in
    ``json.dumps(paths)``: that asked a question about the document's
    shape by looking at its text, so a path description that merely
    mentioned ``#/components/schemas/PaginationMeta`` would have pulled
    the component in.

    Only local schema references are collected. This generator emits no
    other kind, and one appearing would be a bug worth failing on rather
    than resolving -- which ``_component_schemas()`` does.
    """
    found = set()
    if isinstance(node, dict):
        ref = node.get('$ref')
        if isinstance(ref, str):
            found.add(ref)
        for value in node.values():
            found |= _referenced_components(value)
    elif isinstance(node, list):
        for value in node:
            found |= _referenced_components(value)
    return found


def _component_schemas(paths):
    """The ``components.schemas`` entries ``paths`` actually references.

    Only a resource with a list endpoint gets the paginated-list response
    that refs ``PaginationMeta`` (see ``operations._list_responses()``); a
    document of detail-only or function-based-view paths never does, and
    publishing a component nothing points at is dead weight in a document
    served on every reference-page load. Redocly does not object to one --
    its ``recommended`` ruleset has no ``no-unused-components`` -- so this
    is a size decision, not a lint one.

    A reference to a component that is not registered raises. The spec
    would be invalid, and while ``yarn openapi:lint`` does reject a
    dangling ``$ref``, that is only reached if someone lints; failing here
    means ``./manage.py generate_openapi`` cannot write the broken
    document in the first place.
    """
    names = set()
    for ref in _referenced_components(paths):
        if not ref.startswith(_REF_PREFIX):
            raise ValueError(
                f'{ref!r} is not a local component reference; this '
                f'generator emits only {_REF_PREFIX}<name>.'
            )
        names.add(ref[len(_REF_PREFIX):])
    unknown = sorted(names - set(COMPONENT_SCHEMAS))
    if unknown:
        raise ValueError(
            f'paths reference undeclared component schema(s) '
            f'{", ".join(unknown)}. Add them to COMPONENT_SCHEMAS.'
        )
    return {name: COMPONENT_SCHEMAS[name] for name in sorted(names)}


def build_document(paths, *, title, tags=()):
    """Assemble one complete OpenAPI document from an already-final
    ``paths`` mapping.

    ``paths`` must be the *complete* set of paths this document will
    ever contain -- ``components.schemas`` is derived from it right
    here, so a path spliced in afterwards (as the old callers of this
    function used to do for view documents and the bundle) would not be
    reflected in the derived components, silently producing a dangling
    ``$ref`` the moment some path referenced a component that an
    earlier, incomplete ``paths`` did not.
    """
    document = {
        'openapi': OPENAPI_VERSION,
        'info': {
            'title': title,
            'version': '1.0.0',
            'description': 'CommCare data API.',
        },
        'servers': SERVERS,
        'paths': paths,
        'components': {
            'schemas': _component_schemas(paths),
            'securitySchemes': SECURITY_SCHEMES,
        },
        'security': SECURITY_REQUIREMENT,
    }
    if tags:
        document['tags'] = list(tags)
    return document


def _resource_tag(entry):
    """The (name, description) tag pair for a catalogue entry's resource.

    ``name`` matches the tag ``operations.resource_paths()`` attaches to
    every operation for this resource (its Tastypie ``resource_name``), so
    declaring it globally here means every tag an operation uses is a tag
    the document defines, without inventing anything -- the description,
    when there is one, comes straight from the resource's own ``Docs``.
    """
    resource = entry.resource(api_name=entry.version)
    name = resource._meta.resource_name
    docs = collect_docs(entry.resource)
    description = docs.get('description') or docs.get('summary')
    return name, description


def _view_tag(slug, docs):
    """The (name, description) tag pair for a documented function-based
    view, matching the tag ``view_paths()`` attaches to its operations."""
    return slug, (docs.description or docs.summary)


def _merge_tags(pairs):
    """Deduplicate ``(name, description)`` pairs into an OpenAPI ``tags``
    list, preserving first-seen order.

    The first non-empty description seen for a name wins; a later
    occurrence with no description does not blank one out (this matters
    for the bundle, where the same tag name can recur once per
    version of a resource).
    """
    tags = {}
    for name, description in pairs:
        if description and not tags.get(name):
            tags[name] = description
        else:
            tags.setdefault(name, description)
    result = []
    for name, description in tags.items():
        tag = {'name': name}
        if description:
            tag['description'] = description
        result.append(tag)
    return result


def _title(entry):
    docs = collect_docs(entry.resource)
    if docs.get('summary'):
        return docs['summary']
    return entry.doc_slug.replace('-', ' ').title()


def _group_view_docs_by_slug(slug_docs_pairs):
    """Merge every ``(slug, ApiViewDocs)`` pair sharing a slug into one
    ``paths`` mapping and one list of ``(name, description)`` tag pairs
    per slug, in registration order.

    Pulled out of ``build_all()`` so the merge -- paths fully combined
    before any document is built from them, and every view's tag pair
    collected rather than only the first-registered one -- is testable
    without depending on the real catalogue.
    """
    paths_by_slug = {}
    tag_pairs_by_slug = {}
    for slug, docs in slug_docs_pairs:
        paths_by_slug.setdefault(slug, {}).update(
            view_paths(slug, docs)
        )
        tag_pairs_by_slug.setdefault(slug, []).append(
            _view_tag(slug, docs)
        )
    return paths_by_slug, tag_pairs_by_slug


def _view_docs_from_catalogue():
    """``(doc_slug, ApiViewDocs)`` pairs for every catalogued view, in
    catalogue order.

    The catalogue entry's ``doc_slug`` is the only place a view's slug is
    written -- ``ApiViewDocs`` carries none of its own -- so a view's
    entry here is resolved rather than read off the docs object.
    Resolved here rather than at import so that reading the catalogue --
    which happens on the request path -- does not import view modules.
    """
    return [
        (entry.doc_slug, entry.resolve()._openapi_docs)
        for entry in documented_view_entries()
    ]


def build_all():
    """Every documented spec, keyed by ``doc_slug``, plus ``'bundle'``."""
    entries = documented_entries()
    resource_paths_by_entry = {
        entry: resource_paths(entry) for entry in entries
    }
    resource_tags = [_resource_tag(entry) for entry in entries]
    documents = {
        entry.doc_slug: build_document(
            paths,
            title=_title(entry),
            tags=_merge_tags([_resource_tag(entry)]),
        )
        for entry, paths in resource_paths_by_entry.items()
    }

    # More than one decorated view can share a doc_slug (e.g. Case API v2
    # is both `case_api` and the separate `case_api_bulk_fetch` view), so
    # their paths -- and their tag descriptions -- are fully merged
    # *before* a document is built from them. Building a document from
    # only the first view's paths and splicing the rest in afterward
    # (the old approach) derives `components.schemas` from an incomplete
    # `paths`, and only ever sees the first view's `_view_tag()`. The
    # merged document's title is derived from the shared doc_slug rather
    # than from whichever view's `summary` happened to register first,
    # so it doesn't depend on -- or misrepresent -- registration order.
    view_paths_by_slug, view_tag_pairs_by_slug = _group_view_docs_by_slug(
        _view_docs_from_catalogue()
    )

    view_documents = {
        doc_slug: build_document(
            paths,
            title=doc_slug.replace('-', ' ').title(),
            tags=_merge_tags(view_tag_pairs_by_slug[doc_slug]),
        )
        for doc_slug, paths in view_paths_by_slug.items()
    }

    bundle_paths = {}
    for paths in resource_paths_by_entry.values():
        bundle_paths.update(paths)
    for paths in view_paths_by_slug.values():
        bundle_paths.update(paths)
    view_tags = [
        tag
        for pairs in view_tag_pairs_by_slug.values()
        for tag in pairs
    ]
    bundle = build_document(
        bundle_paths,
        title='CommCare Data APIs',
        tags=_merge_tags(resource_tags + view_tags),
    )

    documents.update(view_documents)
    documents['bundle'] = bundle
    return documents
