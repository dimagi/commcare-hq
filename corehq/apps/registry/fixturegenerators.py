from lxml.builder import E

from corehq.apps.domain.models import Domain
from corehq.apps.registry.helper import DataRegistryHelper


def _get_registry_list_fixture(registries):
    registry_elements = [
        _get_registry_element(registry) for registry in registries
    ]
    return E.fixture(
        E.registry_list(*registry_elements),
        id='registry:list'
    )


def _get_registry_domains_fixture(current_domain, registry):
    domains = _get_registry_domains(current_domain, registry)
    return E.fixture(
        E.domains(*domains),
        id=f'registry:domains:{registry.slug}'
    )

def _get_registry_element(registry):
    return E.registry(
        *[E.name(registry.name), E.description(registry.description)],
        slug=registry.slug,
        owner=registry.domain,
        active='true' if registry.is_active else 'false'
    )


def _get_registry_domains(current_domain, registry):
    helper = DataRegistryHelper(current_domain, registry=registry)
    domain_elements = []
    for domain in sorted(list(helper.visible_domains)):
        domain_obj = Domain.get_by_name(domain)
        display_name = domain_obj.display_name() if domain_obj else domain
        domain_elements.append(E.domain(display_name, name=domain))
    return domain_elements
