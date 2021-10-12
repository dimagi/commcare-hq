from lxml.builder import E

from casexml.apps.phone.fixtures import FixtureProvider
from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.util import module_offers_registry_search
from corehq.apps.domain.models import Domain
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.registry.models import DataRegistry
from corehq.apps.registry.utils import RegistryPermissionCheck


class RegistryFixtureProvider(FixtureProvider):
    """Output fixtures for data registries"""
    id = "registry"

    def __call__(self, restore_state):
        if not _should_sync(restore_state):
            return []

        apps = _get_apps(restore_state)
        registry_slugs = {
            module.search_config.data_registry
            for app in apps
            for module in app.get_modules()
            if module_offers_registry_search(module)
        }
        if not registry_slugs:
            return []

        permission_check = _get_permission_checker(restore_state)
        available_registries = {
            registry.slug: registry
            for registry in DataRegistry.objects.visible_to_domain(restore_state.domain)
            if permission_check.can_view_registry_data(registry.slug)
        }
        needed_registries = [
            available_registries[slug] for slug in registry_slugs
            if slug in available_registries
        ]

        fixtures = [_get_registry_list_fixture(needed_registries)]
        for registry in needed_registries:
            fixtures.append(_get_registry_domains_fixture(restore_state.domain, registry))

        return fixtures


registry_fixture_generator = RegistryFixtureProvider()


def _should_sync(restore_state):
    return toggles.DATA_REGISTRY.enabled(restore_state.domain)


def _get_apps(restore_state):
    app_aware_sync_app = restore_state.params.app

    if app_aware_sync_app:
        apps = [app_aware_sync_app]
    else:
        apps = get_apps_in_domain(restore_state.domain, include_remote=False)

    return apps


def _get_permission_checker(restore_state):
    couch_user = restore_state.restore_user._couch_user
    return RegistryPermissionCheck(restore_state.domain, couch_user)


def _get_registry_list_fixture(registries):
    """
    <fixture id="registry:list">
       <registry_list>
           <registry slug="slug1" owner="owning_domain" active="true|false">
               <name></name>
               <description></description>
           </registry>
       </registry_list>
    </fixture>
    """
    registry_elements = [
        _get_registry_element(registry) for registry in registries
    ]
    return E.fixture(
        E.registry_list(*registry_elements),
        id='registry:list'
    )


def _get_registry_domains_fixture(current_domain, registry):
    """
    <fixture id="registry:domains:slug1">
       <domains>
           <domain name="domain1">My Domain</domain>
           <domain name="domain2">domain2</domain>
       </domains>
    </fixture>
    """
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
