from django.core.management.base import BaseCommand

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app_doc, get_app_ids_in_domain
from corehq.toggles import NAMESPACE_DOMAIN


def _module_name(module):
    name = module.get('name', '')
    if isinstance(name, dict):
        name = next(iter(name.values()), '')
    return name or '(unnamed)'


class Command(BaseCommand):
    help = "Migrate to new Case Search toggles"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            help="Show what would be done without actually setting toggles",
            action='store_true',
        )
        parser.add_argument(
            '--verbose',
            help="Show which features triggered each toggle",
            action='store_true',
        )
        parser.add_argument(
            '--domains',
            help="Comma-separated list of domains to process instead of all SYNC_SEARCH_CASE_CLAIM domains",
            type=lambda s: [d.strip() for d in s.split(',')],
        )

    @staticmethod
    def _get_case_list_modules(app_doc):
        return [m for m in app_doc.get('modules', []) if m['module_type'] == 'basic' and m['case_type']]

    @staticmethod
    def _app_uses_normal_case_list_option(app):
        reasons = []

        for m in Command._get_case_list_modules(app):
            search_config = m.get('search_config', {})
            mod = _module_name(m)

            auto_launch = search_config.get('auto_launch', False)
            # Normal Navigation / See More - only if case search is actually configured
            if bool(search_config.get('properties')) and not auto_launch:
                reasons.append(f"module '{mod}': not auto_launch (See More / Normal Case List)")

            if reasons:
                break

        return reasons

    def handle(self, **options):
        dry_run = options.get('dry_run', False)
        verbose = options.get('verbose', False)
        if dry_run:
            self.stdout.write("DRY RUN - No toggles will be set\n")

        domains = options['domains'] or toggles.CASE_SEARCH_DEPRECATED.get_enabled_domains()
        for domain_name in domains:
            normal_case_list_reasons = []
            for app_id in get_app_ids_in_domain(domain_name):
                if normal_case_list_reasons:
                    break

                app = get_app_doc(domain_name, app_id)
                app_label = f"{app['_id']} ({app.get('name', 'unknown')})"

                if not normal_case_list_reasons:
                    app_reasons = Command._app_uses_normal_case_list_option(app)
                    if app_reasons:
                        normal_case_list_reasons = [f"app {app_label}: {r}" for r in app_reasons]

            self.stdout.write(f"for domain '{domain_name}':")
            if normal_case_list_reasons:
                self.stdout.write("  enable CASE_SEARCH_DEPRECATED_NORMAL_CASE_LIST")
                if verbose:
                    for reason in normal_case_list_reasons:
                        self.stdout.write(f"    - {reason}")
                if not dry_run:
                    toggles.CASE_SEARCH_DEPRECATED_NORMAL_CASE_LIST.set(domain_name, True, NAMESPACE_DOMAIN)

            self.stdout.write("\n")
