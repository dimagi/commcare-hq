"""
Feature usage metric calculations (monthly collection).
"""
from django.conf import settings
from django.db.models import Q

from dimagi.utils.couch.cache import cache_core

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.app_manager.const import WORKFLOW_DEFAULT
from corehq.apps.app_manager.util import actions_use_usercase
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.data_cleaning.models import BulkEditSession
from corehq.apps.data_dictionary.models import CaseProperty
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.export.utils import is_dashboard_feed
from corehq.apps.groups.models import Group
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.locations.models import LocationType
from corehq.apps.saved_reports.models import ReportConfig
from corehq.apps.sso.models import IdentityProvider, TrustedIdentityProvider

from .metric_registry import MetricDef


# Application Feature metric calculations

def calc_has_multimedia(domain_context):
    """Check if any app uses multimedia (images, audio, video)."""
    return any(
        bool(getattr(a, 'multimedia_map', {}))
        for a in domain_context.apps
    )


def calc_has_case_management(domain_context):
    """Check if any app has a case list menu (offline case management)."""
    for app in domain_context.apps:
        for module in app.get_modules():
            if getattr(module, 'case_type', ''):
                return True
    return False


def calc_has_eof_navigation(domain_context):
    """Check if any form has non-default end-of-form navigation."""
    for app in domain_context.apps:
        for module in app.get_modules():
            for form in module.get_forms():
                workflow = getattr(
                    form,
                    'post_form_workflow',
                    WORKFLOW_DEFAULT,
                )
                if workflow != WORKFLOW_DEFAULT:
                    return True
    return False


def calc_has_web_apps(domain_context):
    """Check if any app has Web Apps (cloudcare) enabled."""
    return any(
        getattr(a, 'cloudcare_enabled', False)
        for a in domain_context.apps
    )


def calc_has_app_profiles(domain_context):
    """Check if any app has build profiles configured."""
    return any(
        bool(getattr(a, 'build_profiles', {}))
        for a in domain_context.apps
    )


def calc_has_save_to_case(domain_context):
    """Check if any form uses the Save To Case feature.

    Save To Case is a Vellum question type that writes form data to a
    case from inside a repeat group, targeting a case type by reference
    rather than the form's primary case.  It is stored on the form as
    case_references_data and is distinct from ordinary open_case /
    update_case actions.
    """
    for app in domain_context.apps:
        for module in app.get_modules():
            for form in module.get_forms():
                if getattr(form, 'get_save_to_case_updates', None):
                    if form.get_save_to_case_updates():
                        return True
    return False


def calc_bulk_case_editing_sessions(domain_context):
    """Count bulk case editing sessions."""
    return BulkEditSession.objects.filter(domain=domain_context.domain).count()


def calc_has_custom_branding(domain_context):
    """Check for custom branding: domain logo or app logos."""
    if domain_context.domain_obj.has_custom_logo:
        return True
    for app in domain_context.apps:
        if getattr(app, 'logo_refs', None):
            return True
    return False


# Data & Export Feature metric calculations

def calc_has_data_dictionary(domain_context):
    """Check if domain has used data typing in data dictionary."""
    return CaseProperty.objects.filter(
        case_type__domain=domain_context.domain,
    ).exclude(
        data_type=CaseProperty.DataType.UNDEFINED
    ).exists()


def calc_form_exports(domain_context):
    """Count of form data exports."""
    return len(domain_context.form_exports)


def calc_case_exports_only(domain_context):
    """Count of case data exports (excluding form exports)."""
    return len(domain_context.case_exports)


def calc_scheduled_exports(domain_context):
    """Count of scheduled (daily saved) data exports."""
    return sum(e['is_daily_saved_export'] for e in domain_context.exports)


def calc_has_excel_dashboard(domain_context):
    """Returns True if domain has created an Excel dashboard feed"""
    return any(is_dashboard_feed(e) for e in domain_context.exports)


def calc_case_list_explorer_reports(domain_context):
    """Count saved case list explorer reports.

    ReportConfig is a CouchDB document so we query the Couch view
    for all configs in the domain and count those with the matching slug.
    """
    db = ReportConfig.get_db()
    key = ['name slug', domain_context.domain]
    rows = cache_core.cached_view(
        db,
        'reportconfig/configs_by_domain',
        reduce=False,
        include_docs=False,
        startkey=key,
        endkey=key + [{}],
        stale=settings.COUCH_STALE_QUERY,
    )
    return sum(
        1 for row in rows
        if len(row['key']) >= 4 and row['key'][3] == 'case_list_explorer'
    )


def calc_det_configs(domain_context):
    """Count exports with Data Export Tool config enabled."""
    return sum(e['show_det_config_download'] for e in domain_context.exports)


def calc_odata_feeds(domain_context):
    """Count OData feed configurations."""
    return sum(e['is_odata_config'] for e in domain_context.exports)


def calc_linked_domains(domain_context):
    """Count linked project spaces."""
    return DomainLink.objects.filter(
        Q(master_domain=domain_context.domain)
        | Q(linked_domain=domain_context.domain)
    ).count()


def calc_has_case_deduplication(domain_context):
    """Check if domain has at least one deduplication rule."""
    return AutomaticUpdateRule.objects.filter(
        domain=domain_context.domain,
        workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        deleted=False,
    ).exists()


# User & Security Feature metric calculations

def calc_mobile_user_groups(domain_context):
    """Count mobile user groups."""
    return len(Group.by_domain(domain_context.domain))


def calc_has_user_case_management(domain_context):
    """Check if any form uses user case management."""
    for app in domain_context.apps:
        for module in app.get_modules():
            for form in module.get_forms():
                if (
                    hasattr(form, 'actions')
                    and actions_use_usercase(form.actions)
                ):
                    return True
    return False


def calc_has_organization(domain_context):
    """Check if domain has an organization structure (locations)."""
    return LocationType.objects.filter(
        domain=domain_context.domain
    ).exists()


def calc_user_profiles(domain_context):
    """Count user profiles defined."""
    definition = CustomDataFieldsDefinition.get(
        domain_context.domain,
        'UserFields',
    )
    if definition:
        return len(definition.get_profiles())
    return 0


def calc_has_2fa_required(domain_context):
    """Check if domain requires two-factor authentication."""
    return bool(getattr(domain_context.domain_obj, 'two_factor_auth', False))


def calc_has_shortened_timeout(domain_context):
    """Check if domain has shortened inactivity timeout."""
    return bool(getattr(domain_context.domain_obj, 'secure_sessions', False))


def calc_has_strong_passwords(domain_context):
    """Check if domain requires strong mobile passwords."""
    return bool(
        getattr(domain_context.domain_obj, 'strong_mobile_passwords', False)
    )


def calc_has_sso(domain_context):
    """Check if domain has SSO configured.

    A domain is SSO-enabled if either:
    - its BillingAccount owns an active IdentityProvider, or
    - it trusts an active IdentityProvider owned by another account.
    """
    acct = BillingAccount.get_account_by_domain(domain_context.domain)
    if IdentityProvider.objects.filter(owner=acct, is_active=True).exists():
        return True
    return TrustedIdentityProvider.objects.filter(
        domain=domain_context.domain,
        identity_provider__is_active=True,
    ).exists()


FEATURE_METRICS = [
    # Application Features
    MetricDef('has_multimedia', 'cp_has_multimedia',
              # Slow (fetch & cache domain_context.apps)
              calc_has_multimedia),
    MetricDef('has_case_management', 'cp_has_case_management',
              calc_has_case_management),
    MetricDef('has_eof_navigation', 'cp_has_eof_navigation',
              calc_has_eof_navigation),
    MetricDef('has_web_apps', 'cp_has_web_apps',
              calc_has_web_apps),
    MetricDef('has_app_profiles', 'cp_has_app_profiles',
              calc_has_app_profiles),
    MetricDef('has_save_to_case', 'cp_has_save_to_case',
              calc_has_save_to_case),
    MetricDef('bulk_case_editing_sessions',
              'cp_n_bulk_case_editing_sessions',
              calc_bulk_case_editing_sessions, is_boolean=False),
    MetricDef('has_custom_branding', 'cp_has_custom_branding',
              calc_has_custom_branding),

    # Data & Export Features
    MetricDef('has_data_dictionary', 'cp_has_data_dictionary',
              calc_has_data_dictionary),
    MetricDef('form_exports', 'cp_n_form_exports',
              # Slow (fetch & cache domain_context.form_exports)
              calc_form_exports, is_boolean=False),
    MetricDef('case_exports_only', 'cp_n_case_exports_only',
              # Slow (fetch & cache domain_context.case_exports)
              calc_case_exports_only, is_boolean=False),
    MetricDef('scheduled_exports', 'cp_n_scheduled_exports',
              calc_scheduled_exports, is_boolean=False),
    MetricDef('has_excel_dashboard', 'cp_has_excel_dashboard',
              calc_has_excel_dashboard),
    MetricDef('case_list_explorer_reports',
              'cp_n_case_list_explorer_reports',
              calc_case_list_explorer_reports, is_boolean=False),
    MetricDef('det_configs', 'cp_n_det_configs',
              calc_det_configs, is_boolean=False),
    MetricDef('odata_feeds', 'cp_n_odata_feeds',
              calc_odata_feeds, is_boolean=False),
    MetricDef('linked_domains', 'cp_n_linked_domains',
              calc_linked_domains, is_boolean=False),
    MetricDef('has_case_deduplication', 'cp_has_case_deduplication',
              calc_has_case_deduplication),

    # User & Security Features
    MetricDef('mobile_user_groups', 'cp_n_mobile_user_groups',
              calc_mobile_user_groups, is_boolean=False),
    MetricDef('has_user_case_management',
              'cp_has_user_case_management',
              calc_has_user_case_management),
    MetricDef('has_organization', 'cp_has_organization',
              calc_has_organization),
    MetricDef('user_profiles', 'cp_n_user_profiles',
              calc_user_profiles, is_boolean=False),
    MetricDef('has_2fa_required', 'cp_has_2fa_required',
              calc_has_2fa_required),
    MetricDef('has_shortened_timeout', 'cp_has_shortened_timeout',
              calc_has_shortened_timeout),
    MetricDef('has_strong_passwords', 'cp_has_strong_passwords',
              calc_has_strong_passwords),
    MetricDef('has_sso', 'cp_has_sso',
              calc_has_sso),
]
