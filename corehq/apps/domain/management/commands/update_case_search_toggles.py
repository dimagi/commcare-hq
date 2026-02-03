from django.core.management.base import BaseCommand

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app_doc, get_app_ids_in_domain
from corehq.apps.case_search.models import CaseSearchConfig
from corehq.toggles import NAMESPACE_DOMAIN


class Command(BaseCommand):
    help = "Migrate to new Case Search toggles"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            help="Show what would be done without actually setting toggles",
            action='store_true',
        )

    @staticmethod
    def _get_case_list_modules(app_doc):
        return [m for m in app_doc.get('modules', []) if m['module_type'] == 'basic' and m['case_type']]

    @staticmethod
    def _domain_uses_advanced_feature(domain_name):
        csc = CaseSearchConfig.objects.get_or_none(pk=domain_name)
        return (
            toggles.USH_INLINE_SEARCH.enabled(domain_name)
            or toggles.INCREASED_MAX_SEARCH_RESULTS.enabled(domain_name)
            or (csc and csc.synchronous_web_apps)
            or (csc and csc.ignore_patterns.exists())
            or (csc and csc.sync_cases_on_form_entry)
        )

    @staticmethod
    def _app_uses_advanced_feature(app):
        usage_found = False

        for m in Command._get_case_list_modules(app):
            search_config = m.get('search_config', {})
            properties = search_config.get('properties', [])
            default_properties = search_config.get('default_properties', [])

            usage_found |= any([
                p.get('property') == '_xpath_query'
                for p in default_properties
            ])
            usage_found |= any([
                p.get('input_', '') in ['select', 'select1']
                and p.get('itemset', {}).get('instance_id', '').startswith('commcare-reports:')
                for p in properties
            ])
            usage_found |= any([
                p.get('input_', '') == 'checkbox'
                and p.get('itemset', {}).get('instance_id', '').startswith('item-list:')
                for p in properties
            ])
            usage_found |= any([
                p.get('input_') is None
                and not p.get('hidden', False)
                and p.get('appearance') == 'address'
                for p in properties
            ])
            usage_found |= search_config.get('search_on_clear', False)
            usage_found |= any([
                p.get('hidden', False) or p.get('exclude', False)
                for p in properties
            ])
            usage_found |= bool(search_config.get('custom_related_case_property'))
            usage_found |= bool(search_config.get('instance_name'))
            usage_found |= bool(len(search_config.get('custom_sort_properties', [])))

            if usage_found:
                break

        return usage_found

    @staticmethod
    def _domain_uses_deprecated_feature(domain_name):
        return (
            toggles.WEBAPPS_STICKY_SEARCH.enabled(domain_name)
        )

    @staticmethod
    def _app_uses_deprecated_feature(app):
        usage_found = False

        for m in Command._get_case_list_modules(app):
            search_config = m.get('search_config', {})
            auto_launch = search_config.get('auto_launch', False)
            default_search = search_config.get('default_search', False)

            # see more
            usage_found |= not auto_launch and default_search

            usage_found |= bool(search_config.get('additional_relevant'))
            usage_found |= bool(search_config.get('search_filter'))

            if usage_found:
                break

        return usage_found

    @staticmethod
    def _app_uses_related_lookup_feature(app):
        usage_found = False

        for m in Command._get_case_list_modules(app):
            search_config = m.get('search_config', {})
            properties = search_config.get('properties', [])
            default_properties = search_config.get('default_properties', [])

            csql_fns = [
                "ancestor-exists",
                "subcase-exists",
                "subcase-count",
            ]

            usage_found |= any([
                p.get('property') == '_xpath_query'
                and p.get('defaultValue')
                and any([fn in p.get('defaultValue') for fn in csql_fns])
                for p in default_properties
            ])

            usage_found |= any([p['name'].startswith('parent/') for p in properties])
            usage_found |= search_config.get('include_all_related_cases', False)

            if usage_found:
                break

        return usage_found

    def handle(self, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write("DRY RUN - No toggles will be set\n")

        domains = toggles.SYNC_SEARCH_CASE_CLAIM.get_enabled_domains()
        for domain_name in domains:
            uses_case_search_advanced = (
                Command._domain_uses_advanced_feature(domain_name)
            )
            uses_case_search_deprecated = (
                Command._domain_uses_deprecated_feature(domain_name)
            )
            uses_case_search_related_lookup = False

            for app_id in get_app_ids_in_domain(domain_name):
                if (uses_case_search_advanced and uses_case_search_deprecated
                        and uses_case_search_related_lookup):
                    break

                app = get_app_doc(domain_name, app_id)
                uses_case_search_advanced = (
                    uses_case_search_advanced
                    or Command._app_uses_advanced_feature(app)
                )
                uses_case_search_deprecated = (
                    uses_case_search_deprecated
                    or Command._app_uses_deprecated_feature(app)
                )
                uses_case_search_related_lookup = (
                    uses_case_search_related_lookup
                    or Command._app_uses_related_lookup_feature(app)
                )

            self.stdout.write(f"for domain '{domain_name}' enable:")
            if uses_case_search_advanced:
                self.stdout.write("  CASE_SEARCH_ADVANCED")
                if not dry_run:
                    toggles.CASE_SEARCH_ADVANCED.set(domain_name, True, NAMESPACE_DOMAIN)
            if uses_case_search_deprecated:
                self.stdout.write("  CASE_SEARCH_DEPRECATED")
                if not dry_run:
                    toggles.CASE_SEARCH_DEPRECATED.set(domain_name, True, NAMESPACE_DOMAIN)
            if uses_case_search_related_lookup:
                self.stdout.write("  CASE_SEARCH_RELATED_LOOKUPS")
                if not dry_run:
                    toggles.CASE_SEARCH_RELATED_LOOKUPS.set(domain_name, True, NAMESPACE_DOMAIN)

            self.stdout.write("\n")
