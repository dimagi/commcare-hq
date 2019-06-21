# This management command is a one-off and can certainly be removed after say May 2019
from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.management import BaseCommand

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain, get_current_app
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Turn on legacy behavior flag where needed"

    def handle(self, **options):
        flag_legacy_child_module_domains()


def flag_legacy_child_module_domains():
    """Enable the LEGACY_CHILD_MODULES flag for domains that need it"""
    domains = set(toggles.BASIC_CHILD_MODULE.get_enabled_domains() +
                  toggles.APP_BUILDER_ADVANCED.get_enabled_domains())
    for domain in with_progress_bar(domains):
        for app in get_apps(domain):
            if has_misordered_modules(app):
                if needs_legacy_flag(app):
                    toggles.LEGACY_CHILD_MODULES.set(domain, True, toggles.NAMESPACE_DOMAIN)


def get_apps(domain):
    for app_id in get_app_ids_in_domain(domain):
        try:
            app = get_current_app(domain, app_id)
        except Exception:
            pass  # It's not gonna load in app manager anyways
        if not app.is_remote_app():
            yield app


def has_misordered_modules(app):
    last_parent = None
    for module in app.modules:
        if not module.root_module_id:
            last_parent = module.unique_id
        elif module.root_module_id != last_parent:
            return True


def needs_legacy_flag(app):
    return child_before_parent(app) or uses_custom_case_tile_xml(app)


def child_before_parent(app):
    indices_by_uid = {m.unique_id: m.id for m in app.modules}
    return any(
        m.root_module_id and indices_by_uid.get(m.root_module_id, -1) > m.id
        for m in app.modules
    )


def uses_custom_case_tile_xml(app):
    for module in app.modules:
        if hasattr(module, 'case_details'):
            for detail in [module.case_details.short, module.case_details.long]:
                if detail.custom_xml:
                    return True
