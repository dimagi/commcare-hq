from corehq.apps.api.openapi.catalogue import documented_entries
from corehq.apps.api.openapi.docs import collect_docs
from corehq.apps.api.openapi.operations import object_schema

# Every documented resource is in exactly one of these two sets, and
# ``test_every_documented_resource_is_classified`` fails if one is in
# neither -- which is what a new API arriving undocumented looks like.
# An allowlist on its own could not say that: its absences are silent, so
# a slug nobody had got round to and a slug deliberately excluded were
# indistinguishable.
#
# Documented views are out of scope here. This module only reaches
# ``documented_entries()``; a catalogued view is held to
# ``test_view_docs``'s equivalent guard, which is not opt-in.

#: Held to the full standard: every published field described, and a
#: ``Docs`` summary and description. Move a slug up from the backlog when
#: its documentation is written; do not move one down.
DOCUMENTED_SLUGS = frozenset({
    'user-v1',
    'case-v1',
    'form-v1',
    'group-v1',
    'location-v1',
    'location-v2',
    'location-type-v1',
    'lookup-table-v1',
    'lookup-table-item-v1',
    'lookup-table-item-v2',
})

#: Published, but not yet documented to that standard. Each of these must
#: still have at least one gap -- ``test_the_backlog_is_accurate`` proves
#: it, so an API that becomes fully documented cannot be left down here.
#: ``/api/docs/`` shows each one's live coverage.
UNDOCUMENTED_SLUGS = frozenset({
    'application-v1',
    'bulk-user-v1',
    'det-export-v1',
    'fixture-v1',
    'report-config-v1',
    'report-data-v1',
    'sso-v1',
    'user-domains-v1',
    'web-user-v1',
})


def _undocumented_fields(entry):
    """Properties the generated schema publishes without a description.

    Read off the generated schema rather than re-derived from
    ``help_text`` and ``Docs``, so that this cannot disagree with what the
    spec actually says -- a description supplied any way ``object_schema()``
    supplies one (``help_text``, ``field_schemas``, ``added_fields``, or
    ``DEFAULT_FIELD_SCHEMAS``) counts, and only a description that reaches
    the spec does.
    """
    resource = entry.resource(api_name=entry.version)
    schema = object_schema(
        resource.build_schema(), collect_docs(entry.resource)
    )
    return sorted(
        name
        for name, property_schema in schema['properties'].items()
        if not property_schema.get('description')
    )


def _documentation_gaps(entry):
    """Everything that would keep ``entry`` out of ``DOCUMENTED_SLUGS``.

    One definition, used by both the gate and the backlog check. Deriving
    "is this documented?" separately in each would let the two disagree,
    so a slug could satisfy one and not the other and neither test would
    say so.
    """
    gaps = []
    docs = collect_docs(entry.resource)
    if not docs.get('summary'):
        gaps.append('no Docs.summary')
    if not docs.get('description'):
        gaps.append('no Docs.description')
    undescribed = _undocumented_fields(entry)
    if undescribed:
        gaps.append(f'fields with no description: {undescribed}')
    return gaps


def test_every_documented_resource_is_classified():
    """The guard the plain allowlist could not provide.

    A resource added to the catalogue without being classified fails here
    by name, rather than shipping undescribed and unnoticed. The check
    runs both ways, so a slug left behind after its resource is removed
    fails too.
    """
    published = {entry.doc_slug for entry in documented_entries()}
    classified = DOCUMENTED_SLUGS | UNDOCUMENTED_SLUGS
    assert published == classified, (
        'published but unclassified: '
        f'{sorted(published - classified)}; '
        'classified but no longer published: '
        f'{sorted(classified - published)}'
    )


def test_gated_resources_have_no_documentation_gaps():
    failures = {
        entry.doc_slug: gaps
        for entry in documented_entries()
        if entry.doc_slug in DOCUMENTED_SLUGS
        and (gaps := _documentation_gaps(entry))
    }
    assert not failures, f'gated but incomplete: {failures}'


def test_the_backlog_is_accurate():
    """A slug in ``UNDOCUMENTED_SLUGS`` must really be undocumented.

    Otherwise finishing an API's documentation leaves it sitting in the
    backlog, still ungated, and nothing points that out -- the same silent
    gap in the other direction.
    """
    finished = [
        entry.doc_slug
        for entry in documented_entries()
        if entry.doc_slug in UNDOCUMENTED_SLUGS
        and not _documentation_gaps(entry)
    ]
    assert not finished, (
        f'{sorted(finished)} now meet the standard -- move them from '
        f'UNDOCUMENTED_SLUGS to DOCUMENTED_SLUGS'
    )


def test_declared_examples_exist_on_disk():
    from pathlib import Path

    from corehq.apps.api import openapi

    examples_dir = Path(openapi.__file__).parent / 'examples'
    for entry in documented_entries():
        for name, relative in (
            collect_docs(entry.resource).get('examples', {}).items()
        ):
            assert (examples_dir / relative).exists(), (
                f'{entry.doc_slug} example {name!r} missing: {relative}'
            )
