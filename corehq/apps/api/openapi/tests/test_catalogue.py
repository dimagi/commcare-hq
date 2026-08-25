from corehq.apps.api.openapi.catalogue import (
    CATALOGUE,
    documented_entries,
    entries_for_scope,
)


def test_every_entry_has_a_known_scope():
    assert {e.scope for e in CATALOGUE} <= {'domain', 'user'}


def test_domain_entries_are_in_routing_order():
    names = [
        (e.resource(api_name=e.version)._meta.resource_name, e.version)
        for e in entries_for_scope('domain')
    ]
    assert names[:4] == [
        ('application', 'v1'),
        ('case', 'v1'),
        ('form', 'v1'),
        ('sso', 'v1'),
    ]
    assert ('location', 'v2') in names
    assert ('det_export_instance', 'v1') in names


def test_documented_entries_are_a_subset_with_unique_slugs():
    documented = documented_entries()
    assert documented, 'expected at least one documented entry'
    assert set(documented) <= set(CATALOGUE)
    slugs = [e.doc_slug for e in documented]
    assert len(slugs) == len(set(slugs))


def test_user_scoped_entries():
    names = [
        (e.resource(api_name=e.version)._meta.resource_name, e.version)
        for e in entries_for_scope('user')
    ]
    assert names == [('identity', 'v1'), ('user_domains', 'v1')]


def test_operation_ids_are_unique_across_the_catalogue():
    """``operationId`` is built from ``(resource_name, version)``.

    ``openapi-spec-validator`` does not reject duplicate ``operationId``
    values, but they are invalid OpenAPI and silently break code
    generators, so the catalogue must not contain two entries that would
    produce the same one.
    """
    seen = {}
    duplicates = []
    for entry in CATALOGUE:
        resource_name = entry.resource(
            api_name=entry.version
        )._meta.resource_name
        key = (resource_name, entry.version)
        if key in seen:
            duplicates.append(key)
        seen[key] = entry
    assert not duplicates, (
        f'duplicate (resource_name, version) pairs: {duplicates}'
    )


def test_every_view_entry_resolves_to_a_documented_view():
    # Replaces the old failure mode: a documented view whose module was
    # missing from load_view_docs()'s hard-coded import list generated a
    # spec that the serving views then 404ed on.
    from corehq.apps.api.openapi.catalogue import VIEW_CATALOGUE

    for entry in VIEW_CATALOGUE:
        view = entry.resolve()
        assert hasattr(view, '_openapi_docs'), (
            f'{entry.view} is in VIEW_CATALOGUE but carries no @api_docs'
        )


def test_documented_slugs_covers_resources_and_views():
    from corehq.apps.api.openapi.catalogue import (
        VIEW_CATALOGUE,
        documented_entries,
        documented_slugs,
    )

    slugs = documented_slugs()
    assert slugs == (
        {entry.doc_slug for entry in documented_entries()}
        | {entry.doc_slug for entry in VIEW_CATALOGUE}
    )
    assert 'case-v2' in slugs


def test_resource_and_view_slugs_are_disjoint():
    """``build_all()`` does ``documents.update(view_documents)``, so a
    view slug colliding with a resource slug would silently overwrite the
    resource's document. The two registries must never share a slug."""
    from corehq.apps.api.openapi.catalogue import (
        VIEW_CATALOGUE,
        documented_entries,
    )

    resource_slugs = {entry.doc_slug for entry in documented_entries()}
    view_slugs = {entry.doc_slug for entry in VIEW_CATALOGUE}
    assert not (resource_slugs & view_slugs)


def test_every_catalogued_resource_can_build_a_schema():
    """The generator depends on this for every resource in the catalogue.

    Note this is ``build_schema()`` called in-process. Tastypie's own
    ``.../schema/`` HTTP endpoint is separately broken for resources that
    are not ``ModelResource`` subclasses -- ``get_schema()`` calls
    ``get_object_list()``, which those resources do not implement, so the
    endpoint 500s. That is a pre-existing bug this generator sidesteps
    rather than inherits.
    """
    failures = {}
    for entry in CATALOGUE:
        resource = entry.resource(api_name=entry.version)
        try:
            schema = resource.build_schema()
        except Exception as exc:
            failures[entry.resource.__name__] = repr(exc)
            continue
        assert schema['fields'], entry.resource.__name__
    assert not failures
