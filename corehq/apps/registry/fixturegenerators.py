from lxml.builder import E


def _get_registry_list_fixture(registries):
    registry_elements = [
        _get_registry_element(registry) for registry in registries
    ]
    return E.fixture(
        E.registry_list(*registry_elements),
        id='registry:list'
    )


def _get_registry_element(registry):
    return E.registry(
        *[E.name(registry.name), E.description(registry.description)],
        slug=registry.slug,
        owner=registry.domain,
        active='true' if registry.is_active else 'false'
    )
