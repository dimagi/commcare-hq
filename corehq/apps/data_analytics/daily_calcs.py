"""
Daily metric calculation functions.
"""
from datetime import datetime

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.dbaccessors import domain_has_apps
from corehq.apps.domain.calculations import (
    _get_domain_apps,
    active,
    active_mobile_users,
    cases,
    cases_in_last,
    first_domain_for_user,
    first_form_submission,
    forms,
    forms_in_last,
    get_300th_form_submission_received,
    inactive_cases_in_last,
    last_form_submission,
    sms,
    sms_in_in_last,
    sms_in_last,
    sms_in_last_bool,
    sms_out_in_last,
)
from corehq.apps.es.forms import FormES
from corehq.apps.export.dbaccessors import get_export_count_by_domain
from corehq.apps.fixtures.models import LookupTable
from corehq.apps.groups.models import Group
from corehq.apps.hqmedia.models import ApplicationMediaMixin
from corehq.apps.locations.analytics import users_have_locations
from corehq.apps.locations.models import LocationType
from corehq.apps.sms.models import INCOMING, OUTGOING, SQLMobileBackend
from corehq.apps.userreports.util import (
    number_of_report_builder_reports,
    number_of_ucr_reports,
)
from corehq.apps.users.models import CouchUser, UserRole
from corehq.apps.users.role_utils import get_custom_roles_for_domain
from corehq.apps.users.util import WEIRD_USER_IDS
from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
from corehq.motech.repeaters.models import Repeater

from .metric_registry import MetricDef


def _calc_web_users(ctx):
    return int(ctx.all_stats["web_users"].get(ctx.domain, 0))


def _calc_active_mobile_workers(ctx):
    return int(active_mobile_users(ctx.domain))


def _calc_active_mobile_workers_365(ctx):
    return int(active_mobile_users(ctx.domain, 365))


def _calc_mobile_workers(ctx):
    return int(ctx.all_stats["commcare_users"].get(ctx.domain, 0))


def _calc_active_cases(ctx):
    return int(cases_in_last(ctx.domain, 120))


def _calc_users_with_submission(ctx):
    """Get total number of users who've ever submitted a form in a domain."""
    query = FormES().domain(ctx.domain).user_aggregation()
    terms = {
        user_id for user_id in query.run().aggregations.user.keys
        if user_id not in WEIRD_USER_IDS
    }
    user_ids = terms.intersection(set(CouchUser.ids_by_domain(ctx.domain)))
    return len(user_ids)


def _calc_inactive_cases(ctx):
    return int(inactive_cases_in_last(ctx.domain, 120))


def _calc_cases_30d(ctx):
    return int(cases_in_last(ctx.domain, 30))


def _calc_cases_60d(ctx):
    return int(cases_in_last(ctx.domain, 60))


def _calc_cases_90d(ctx):
    return int(cases_in_last(ctx.domain, 90))


def _calc_cases(ctx):
    return int(cases(ctx.domain))


def _calc_forms(ctx):
    return int(forms(ctx.domain))


def _calc_forms_30d(ctx):
    return int(forms_in_last(ctx.domain, 30))


def _calc_forms_60d(ctx):
    return int(forms_in_last(ctx.domain, 60))


def _calc_forms_90d(ctx):
    return int(forms_in_last(ctx.domain, 90))


def _calc_first_domain(ctx):
    return first_domain_for_user(ctx.domain)


def _calc_first_form(ctx):
    return first_form_submission(ctx.domain, display=False)


def _calc_last_form(ctx):
    return last_form_submission(ctx.domain, display=False)


def _calc_is_active(ctx):
    return active(ctx.domain)


def _calc_has_app(ctx):
    return domain_has_apps(ctx.domain)


def _calc_last_updated(ctx):
    return json_format_datetime(datetime.utcnow())


def _calc_incoming_sms(ctx):
    return int(sms(ctx.domain, INCOMING))


def _calc_outgoing_sms(ctx):
    return int(sms(ctx.domain, OUTGOING))


def _calc_total_sms(ctx):
    return int(sms_in_last(ctx.domain))


def _calc_sms_30d(ctx):
    return int(sms_in_last(ctx.domain, 30))


def _calc_sms_60d(ctx):
    return int(sms_in_last(ctx.domain, 60))


def _calc_sms_90d(ctx):
    return int(sms_in_last(ctx.domain, 90))


def _calc_has_used_sms(ctx):
    return sms_in_last_bool(ctx.domain)


def _calc_has_used_sms_30d(ctx):
    return sms_in_last_bool(ctx.domain, 30)


def _calc_incoming_sms_30d(ctx):
    return int(sms_in_in_last(ctx.domain, 30))


def _calc_incoming_sms_60d(ctx):
    return int(sms_in_in_last(ctx.domain, 60))


def _calc_incoming_sms_90d(ctx):
    return int(sms_in_in_last(ctx.domain, 90))


def _calc_outgoing_sms_30d(ctx):
    return int(sms_out_in_last(ctx.domain, 30))


def _calc_outgoing_sms_60d(ctx):
    return int(sms_out_in_last(ctx.domain, 60))


def _calc_outgoing_sms_90d(ctx):
    return int(sms_out_in_last(ctx.domain, 90))


def _calc_300th_form(ctx):
    return get_300th_form_submission_received(ctx.domain)


def _calc_usercases_30d(ctx):
    return cases_in_last(ctx.domain, 30, case_type=USERCASE_TYPE)


def _calc_telerivet(ctx):
    backends = SQLMobileBackend.get_domain_backends(
        SQLMobileBackend.SMS,
        ctx.domain,
    )
    return len([b for b in backends if isinstance(b, SQLTelerivetBackend)])


def _calc_security_settings(ctx):
    return any(
        getattr(ctx.domain_obj, attr, False)
        for attr in ['two_factor_auth', 'secure_sessions', 'strong_mobile_passwords']
    )


def _calc_custom_roles(ctx):
    return len(get_custom_roles_for_domain(ctx.domain))


def _calc_has_locations(ctx):
    return users_have_locations(ctx.domain)


def _calc_loc_restricted_roles(ctx):
    roles = [r for r in UserRole.objects.get_by_domain(ctx.domain)
             if not r.permissions.access_all_locations]
    return len(roles)


def _calc_case_sharing_locs(ctx):
    return len([lt for lt in LocationType.objects.by_domain(ctx.domain)
                if lt.shares_cases])


def _calc_case_sharing_groups(ctx):
    return len([g for g in Group.by_domain(ctx.domain) if g.case_sharing])


def _calc_repeaters(ctx):
    return Repeater.objects.filter(domain=ctx.domain).count()


def _calc_case_exports(ctx):
    return len(ctx.form_exports + ctx.case_exports)


def _calc_deid_exports(ctx):
    return sum(
        e.get('is_deidentified', False)
        for e in ctx.form_exports + ctx.case_exports
    )


def _calc_saved_exports(ctx):
    return sum(
        e.get('is_daily_saved_export', False)
        for e in ctx.form_exports + ctx.case_exports
    )


def _calc_rb_reports(ctx):
    return number_of_report_builder_reports(ctx.domain)


def _calc_ucrs(ctx):
    return number_of_ucr_reports(ctx.domain)


def _calc_lookup_tables(ctx):
    return LookupTable.objects.by_domain(ctx.domain).count()


def _calc_project_icon(ctx):
    return ctx.domain_obj.has_custom_logo


def _calc_apps_with_icon(ctx):
    return len([a for a in ctx.apps
                if isinstance(a, ApplicationMediaMixin) and a.logo_refs])


def _calc_apps(ctx):
    return len(_get_domain_apps(ctx.domain))


def _calc_apps_multi_lang(ctx):
    return len([a for a in ctx.apps if len(a.langs) > 1])


def _calc_custom_exports(ctx):
    return get_export_count_by_domain(ctx.domain)


DAILY_METRICS = [
    # User Metrics
    MetricDef('web_users', 'cp_n_web_users',
              _calc_web_users, is_boolean=False, schedule='daily'),
    MetricDef('active_mobile_workers', 'cp_n_active_cc_users',
              _calc_active_mobile_workers, is_boolean=False, schedule='daily'),
    MetricDef('active_mobile_workers_in_last_365_days',
              'cp_n_active_cc_users_365_days',
              _calc_active_mobile_workers_365, is_boolean=False,
              schedule='daily'),
    MetricDef('mobile_workers', 'cp_n_cc_users',
              _calc_mobile_workers, is_boolean=False, schedule='daily'),
    MetricDef('users_with_submission', 'cp_n_users_submitted_form',
              _calc_users_with_submission, is_boolean=False, schedule='daily'),
    MetricDef('custom_roles', 'cp_n_custom_roles',
              _calc_custom_roles, is_boolean=False, schedule='daily'),
    MetricDef('has_users_with_location', 'cp_using_locations',
              _calc_has_locations, schedule='daily'),
    MetricDef('location_restricted_roles', 'cp_n_loc_restricted_roles',
              _calc_loc_restricted_roles, is_boolean=False, schedule='daily'),

    # Case Metrics
    MetricDef('active_cases', 'cp_n_active_cases',
              _calc_active_cases, is_boolean=False, schedule='daily'),
    MetricDef('inactive_cases', 'cp_n_inactive_cases',
              _calc_inactive_cases, is_boolean=False, schedule='daily'),
    MetricDef('cases_modified_in_last_30_days', 'cp_n_30_day_cases',
              _calc_cases_30d, is_boolean=False, schedule='daily'),
    MetricDef('cases_modified_in_last_60_days', 'cp_n_60_day_cases',
              _calc_cases_60d, is_boolean=False, schedule='daily'),
    MetricDef('cases_modified_in_last_90_days', 'cp_n_90_day_cases',
              _calc_cases_90d, is_boolean=False, schedule='daily'),
    MetricDef('cases', 'cp_n_cases',
              _calc_cases, is_boolean=False, schedule='daily'),
    MetricDef('usercases_modified_in_last_30_days',
              'cp_n_30_day_user_cases',
              _calc_usercases_30d, is_boolean=False, schedule='daily'),
    MetricDef('case_sharing_locations', 'cp_n_case_sharing_olevels',
              _calc_case_sharing_locs, is_boolean=False, schedule='daily'),
    MetricDef('case_sharing_groups', 'cp_n_case_sharing_groups',
              _calc_case_sharing_groups, is_boolean=False, schedule='daily'),

    # Form Metrics
    MetricDef('forms', 'cp_n_forms',
              _calc_forms, is_boolean=False, schedule='daily'),
    MetricDef('forms_submitted_in_last_30_days', 'cp_n_forms_30_d',
              _calc_forms_30d, is_boolean=False, schedule='daily'),
    MetricDef('forms_submitted_in_last_60_days', 'cp_n_forms_60_d',
              _calc_forms_60d, is_boolean=False, schedule='daily'),
    MetricDef('forms_submitted_in_last_90_days', 'cp_n_forms_90_d',
              _calc_forms_90d, is_boolean=False, schedule='daily'),
    MetricDef('first_form_submission', 'cp_first_form',
              _calc_first_form, is_boolean=False, schedule='daily'),
    MetricDef('most_recent_form_submission', 'cp_last_form',
              _calc_last_form, is_boolean=False, schedule='daily'),
    MetricDef('three_hundredth_form_submission', 'cp_300th_form',
              _calc_300th_form, is_boolean=False, schedule='daily'),

    # Domain Metadata
    MetricDef('is_first_domain_for_creating_user',
              'cp_first_domain_for_user',
              _calc_first_domain, schedule='daily'),
    MetricDef('is_active', 'cp_is_active',
              _calc_is_active, schedule='daily'),
    MetricDef('has_project_icon', 'cp_has_project_icon',
              _calc_project_icon, schedule='daily'),
    MetricDef('has_security_settings', 'cp_use_domain_security',
              _calc_security_settings, schedule='daily'),
    MetricDef('last_modified', 'cp_last_updated',
              _calc_last_updated, is_boolean=False, schedule='daily'),

    # SMS Metrics
    MetricDef('incoming_sms', 'cp_n_in_sms',
              _calc_incoming_sms, is_boolean=False, schedule='daily'),
    MetricDef('outgoing_sms', 'cp_n_out_sms',
              _calc_outgoing_sms, is_boolean=False, schedule='daily'),
    MetricDef('total_sms', 'cp_n_sms_ever',
              _calc_total_sms, is_boolean=False, schedule='daily'),
    MetricDef('sms_in_last_30_days', 'cp_n_sms_30_d',
              _calc_sms_30d, is_boolean=False, schedule='daily'),
    MetricDef('sms_in_last_60_days', 'cp_n_sms_60_d',
              _calc_sms_60d, is_boolean=False, schedule='daily'),
    MetricDef('sms_in_last_90_days', 'cp_n_sms_90_d',
              _calc_sms_90d, is_boolean=False, schedule='daily'),
    MetricDef('has_used_sms', 'cp_sms_ever',
              _calc_has_used_sms, schedule='daily'),
    MetricDef('has_used_sms_in_last_30_days', 'cp_sms_30_d',
              _calc_has_used_sms_30d, schedule='daily'),
    MetricDef('incoming_sms_in_last_30_days', 'cp_n_sms_in_30_d',
              _calc_incoming_sms_30d, is_boolean=False, schedule='daily'),
    MetricDef('incoming_sms_in_last_60_days', 'cp_n_sms_in_60_d',
              _calc_incoming_sms_60d, is_boolean=False, schedule='daily'),
    MetricDef('incoming_sms_in_last_90_days', 'cp_n_sms_in_90_d',
              _calc_incoming_sms_90d, is_boolean=False, schedule='daily'),
    MetricDef('outgoing_sms_in_last_30_days', 'cp_n_sms_out_30_d',
              _calc_outgoing_sms_30d, is_boolean=False, schedule='daily'),
    MetricDef('outgoing_sms_in_last_60_days', 'cp_n_sms_out_60_d',
              _calc_outgoing_sms_60d, is_boolean=False, schedule='daily'),
    MetricDef('outgoing_sms_in_last_90_days', 'cp_n_sms_out_90_d',
              _calc_outgoing_sms_90d, is_boolean=False, schedule='daily'),
    MetricDef('telerivet_backends', 'cp_n_trivet_backends',
              _calc_telerivet, is_boolean=False, schedule='daily'),

    # App Metrics
    MetricDef('has_app', 'cp_has_app',
              _calc_has_app, schedule='daily'),
    MetricDef('apps', 'cp_n_apps',
              _calc_apps, is_boolean=False, schedule='daily'),
    MetricDef('apps_with_icon', 'cp_n_apps_with_icon',
              _calc_apps_with_icon, is_boolean=False, schedule='daily'),
    MetricDef('apps_with_multiple_languages', 'cp_n_apps_with_multi_lang',
              _calc_apps_multi_lang, is_boolean=False, schedule='daily'),

    # Export Metrics
    MetricDef('case_exports', 'cp_n_case_exports',
              _calc_case_exports, is_boolean=False, schedule='daily'),
    MetricDef('deid_exports', 'cp_n_deid_exports',
              _calc_deid_exports, is_boolean=False, schedule='daily'),
    MetricDef('saved_exports', 'cp_n_saved_exports',
              _calc_saved_exports, is_boolean=False, schedule='daily'),
    MetricDef('custom_exports', 'cp_n_saved_custom_exports',
              _calc_custom_exports, is_boolean=False, schedule='daily'),

    # Report/Integration Metrics
    MetricDef('repeaters', 'cp_n_repeaters',
              _calc_repeaters, is_boolean=False, schedule='daily'),
    MetricDef('report_builder_reports', 'cp_n_rb_reports',
              _calc_rb_reports, is_boolean=False, schedule='daily'),
    MetricDef('ucrs', 'cp_n_ucr_reports',
              _calc_ucrs, is_boolean=False, schedule='daily'),
    MetricDef('lookup_tables', 'cp_n_lookup_tables',
              _calc_lookup_tables, is_boolean=False, schedule='daily'),
]

# Fields that are @property on DomainMetrics or auto-managed by Django;
# these should not be written via update_or_create defaults.
_MODEL_MANAGED_FIELDS = frozenset({
    'has_app',
    'has_used_sms',
    'has_used_sms_in_last_30_days',
    'last_modified',
})
