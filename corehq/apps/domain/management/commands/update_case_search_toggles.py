from django.core.management.base import BaseCommand

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app_doc, get_app_ids_in_domain
from corehq.apps.case_search.models import CaseSearchConfig
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
    def _domain_uses_advanced_feature(domain_name):
        reasons = []
        csc = CaseSearchConfig.objects.get_or_none(pk=domain_name)
        # USH Specific toggle to making case search user input available to other parts of the app.
        if toggles.USH_INLINE_SEARCH.enabled(domain_name):
            reasons.append("toggle USH_INLINE_SEARCH")
        if csc and csc.synchronous_web_apps:  # Synchronous Web Apps Submissions
            reasons.append("synchronous_web_apps")
        if csc and csc.ignore_patterns.exists():  # Remove Special Characters
            reasons.append("ignore_patterns (Remove Special Characters)")
        if csc and csc.sync_cases_on_form_entry:  # Sync before entering form
            reasons.append("sync_cases_on_form_entry")
        return reasons

    @staticmethod
    def _app_uses_advanced_feature(app):
        reasons = []

        for m in Command._get_case_list_modules(app):
            search_config = m.get('search_config', {})
            properties = search_config.get('properties', [])
            default_properties = search_config.get('default_properties', [])
            mod = _module_name(m)

            # _xpath_query
            if any(p.get('property') == '_xpath_query' for p in default_properties):
                reasons.append(f"module '{mod}': xpath_query default property")
            # Mobile Report Dropdown
            if any(
                p.get('input_', '') in ['select', 'select1']
                and p.get('itemset', {}).get('instance_id', '').startswith('commcare-reports:')
                for p in properties
            ):
                reasons.append(f"module '{mod}': mobile report search field")
            # Checkbox selections
            if any(
                p.get('input_', '') == 'checkbox'
                and p.get('itemset', {}).get('instance_id', '').startswith('item-list:')
                for p in properties
            ):
                reasons.append(f"module '{mod}': checkbox search field")
            # Geocoder Widget
            if any(
                p.get('input_') is None and p.get('appearance') == 'address'
                for p in properties
            ):
                reasons.append(f"module '{mod}': geocoder search field")
            # Default Value Expressions
            if any(
                bool(p.get('default_value'))
                for p in properties
            ):
                reasons.append(f"module '{mod}': default expression")
            # Clearing search terms resets search results
            if search_config.get('search_on_clear', False):
                reasons.append(f"module '{mod}': search_on_clear")
            # Hide Property on Search Screen / Exclude from Search Filters
            if any(p.get('hidden', False) or p.get('exclude', False) for p in properties):
                reasons.append(f"module '{mod}': hidden/excluded property")
            # Case property with additional case id to add to results
            if search_config.get('custom_related_case_property'):
                reasons.append(f"module '{mod}': custom_related_case_property")
            # Custom search input instance name
            if search_config.get('instance_name'):
                reasons.append(f"module '{mod}': instance_name")
            # Additional Case List and Case Search Types
            if search_config.get('additional_case_types'):
                reasons.append(f"module '{mod}': additional_case_types")
            # Custom Search Sort Properties
            if search_config.get('custom_sort_properties'):
                reasons.append(f"module '{mod}': custom_sort_properties")
            # Multiple Select Case List / Auto-select case search results
            if m.get('case_details', {}).get('short', {}).get('multi_select', False):
                reasons.append(f"module '{mod}': multi_select")

            if reasons:
                break

        return reasons

    @staticmethod
    def _app_uses_deprecated_feature(app):
        reasons = []

        for m in Command._get_case_list_modules(app):
            search_config = m.get('search_config', {})
            mod = _module_name(m)

            auto_launch = search_config.get('auto_launch', False)
            # Normal Navigation / See More - only if case search is actually configured
            if bool(search_config.get('properties')) and not auto_launch:
                reasons.append(f"module '{mod}': not auto_launch (See More / Normal Case List)")
            # Label for searching
            command_label = search_config.get('command_label', {})
            if command_label and command_label != {'en': 'Search All Cases'}:
                reasons.append(f"module '{mod}': command_label")
            if search_config.get('additional_relevant'):  # Claim condition
                reasons.append(f"module '{mod}': additional_relevant (claim condition)")
            # USH Specific toggle to use Search Filter in case search options.
            if search_config.get('search_filter'):
                reasons.append(f"module '{mod}': search_filter")

            if reasons:
                break

        return reasons

    @staticmethod
    def _app_uses_related_lookup_feature(app):
        reasons = []
        csql_fns = [
            "ancestor-exists",  # CSQL Expression: ancestor-exists
            "subcase-exists",   # CSQL Expression: subcase-exists
            "subcase-count",    # CSQL Expression: subcase-count
            "parent/"           # Related properties
        ]

        def is_parent_reference(prop):
            return prop.startswith('parent/') and prop.removeprefix('parent/') != '@case_id'

        for m in Command._get_case_list_modules(app):
            search_config = m.get('search_config', {})
            properties = search_config.get('properties', [])
            default_properties = search_config.get('default_properties', [])
            mod = _module_name(m)

            # CSQL Expression: ancestor-exists / subcase-exists / subcase-count
            # Related properties (via xpath_query)
            for p in default_properties:
                if (
                    p.get('property') == '_xpath_query'
                    and p.get('defaultValue')
                    and any(fn in p['defaultValue'] for fn in csql_fns)
                ):
                    matched = [fn for fn in csql_fns if fn in p['defaultValue']]
                    reasons.append(f"module '{mod}': xpath_query default with {matched}")

            # Related properties
            if any(is_parent_reference(p['name']) for p in properties):
                reasons.append(f"module '{mod}': parent/ search property")
            # Related properties
            if any(is_parent_reference(p.get('property', '')) for p in default_properties):
                reasons.append(f"module '{mod}': parent/ default property")
            # Include related cases in search results
            if search_config.get('include_all_related_cases', False):
                reasons.append(f"module '{mod}': include_all_related_cases")

            if reasons:
                break

        return reasons

    def handle(self, **options):
        dry_run = options.get('dry_run', False)
        verbose = options.get('verbose', False)
        if dry_run:
            self.stdout.write("DRY RUN - No toggles will be set\n")

        domains = options['domains'] or toggles.SYNC_SEARCH_CASE_CLAIM.get_enabled_domains()
        for domain_name in domains:
            advanced_reasons = Command._domain_uses_advanced_feature(domain_name)
            if advanced_reasons:
                advanced_reasons = [f"domain: {r}" for r in advanced_reasons]

            deprecated_reasons = []
            related_lookup_reasons = []
            for app_id in get_app_ids_in_domain(domain_name):
                if advanced_reasons and deprecated_reasons and related_lookup_reasons:
                    break

                app = get_app_doc(domain_name, app_id)
                app_label = f"{app['_id']} ({app.get('name', 'unknown')})"

                if not advanced_reasons:
                    app_reasons = Command._app_uses_advanced_feature(app)
                    if app_reasons:
                        advanced_reasons = [f"app {app_label}: {r}" for r in app_reasons]

                if not deprecated_reasons:
                    app_reasons = Command._app_uses_deprecated_feature(app)
                    if app_reasons:
                        deprecated_reasons = [f"app {app_label}: {r}" for r in app_reasons]

                if not related_lookup_reasons:
                    app_reasons = Command._app_uses_related_lookup_feature(app)
                    if app_reasons:
                        related_lookup_reasons = [f"app {app_label}: {r}" for r in app_reasons]

            self.stdout.write(f"for domain '{domain_name}' enable:")
            if advanced_reasons:
                self.stdout.write("  CASE_SEARCH_ADVANCED")
                if verbose:
                    for reason in advanced_reasons:
                        self.stdout.write(f"    - {reason}")
                if not dry_run:
                    toggles.CASE_SEARCH_ADVANCED.set(domain_name, True, NAMESPACE_DOMAIN)
            if deprecated_reasons:
                self.stdout.write("  CASE_SEARCH_DEPRECATED")
                if verbose:
                    for reason in deprecated_reasons:
                        self.stdout.write(f"    - {reason}")
                if not dry_run:
                    toggles.CASE_SEARCH_DEPRECATED.set(domain_name, True, NAMESPACE_DOMAIN)
            if related_lookup_reasons:
                self.stdout.write("  CASE_SEARCH_RELATED_LOOKUPS")
                if verbose:
                    for reason in related_lookup_reasons:
                        self.stdout.write(f"    - {reason}")
                if not dry_run:
                    toggles.CASE_SEARCH_RELATED_LOOKUPS.set(domain_name, True, NAMESPACE_DOMAIN)

            self.stdout.write("\n")
