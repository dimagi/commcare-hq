from collections import defaultdict
from datetime import date, datetime, timedelta

from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from dateutil.relativedelta import relativedelta

from couchforms.analytics import (
    domain_has_submission_in_last_30_days,
    get_first_form_submission_received,
    get_last_form_submission_received,
    get_number_of_forms_in_domain,
)
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.app_manager.dbaccessors import domain_has_apps
from corehq.apps.data_analytics.esaccessors import get_mobile_users
from corehq.apps.domain.models import Domain
from corehq.apps.es.cases import CaseES
from corehq.apps.es.forms import FormES
from corehq.apps.es.sms import SMSES
from corehq.apps.export.dbaccessors import (
    get_case_exports_by_domain,
    get_export_count_by_domain,
    get_form_exports_by_domain,
)
from corehq.apps.fixtures.models import LookupTable
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.analytics import get_number_of_cases_in_domain
from corehq.apps.hqmedia.models import ApplicationMediaMixin
from corehq.apps.locations.analytics import users_have_locations
from corehq.apps.locations.models import LocationType
from corehq.apps.sms.models import INCOMING, OUTGOING, SQLMobileBackend
from corehq.apps.userreports.util import (
    number_of_report_builder_reports,
    number_of_ucr_reports,
)
from corehq.apps.users.dbaccessors import (
    get_mobile_user_count,
    get_web_user_count,
)
from corehq.apps.users.models import CouchUser, UserRole
from corehq.apps.users.role_utils import get_custom_roles_for_domain
from corehq.apps.users.util import WEIRD_USER_IDS
from corehq.messaging.scheduling.util import domain_has_reminders
from corehq.motech.repeaters.models import Repeater
from corehq.util.dates import iso_string_to_datetime
from corehq.util.quickcache import quickcache


def num_web_users(domain, *args):
    return get_web_user_count(domain, include_inactive=False)


def num_mobile_users(domain, *args):
    return get_mobile_user_count(domain, include_inactive=False)


DISPLAY_DATE_FORMAT = '%Y/%m/%d %H:%M:%S'


def active_mobile_users(domain, days=30):
    return _mobile_users(domain, int(days), inactive=False)


def inactive_mobile_users(domain, days=30):
    return _mobile_users(domain, int(days), inactive=True)


def _mobile_users(domain, days=30, inactive=False):
    """
    Returns the number of mobile users who have submitted a form or SMS
    """
    now = datetime.utcnow()
    then = (now - timedelta(days=days))

    user_ids = get_mobile_users(domain)

    form_users = set(
        FormES()
        .domain(domain)
        .user_aggregation()
        .submitted(gte=then)
        .user_id(user_ids)
        .size(0)
        .run()
        .aggregations.user.keys
    )

    sms_users = set(
        SMSES()
        .incoming_messages()
        .user_aggregation()
        .to_commcare_user()
        .domain(domain)
        .received(gte=then)
        .size(0)
        .run()
        .aggregations.user.keys
    )

    num_users = len(form_users | sms_users)
    return num_users if not inactive else len(user_ids) - num_users


def cases(domain, *args):
    return get_number_of_cases_in_domain(domain)


def cases_in_last(domain, days, case_type=None):
    """
    Returns the number of open cases that have been modified in the last <days> days
    """
    now = datetime.utcnow()
    then = json_format_datetime(now - timedelta(days=int(days)))
    now = json_format_datetime(now)

    query = CaseES().domain(domain).modified_range(gte=then, lte=now).is_closed(False)
    if case_type:
        query = query.case_type(case_type)
    return query.count()


def inactive_cases_in_last(domain, days):
    """
    Returns the number of open cases that have been modified in the last <days> days
    """
    now = datetime.utcnow()
    then = json_format_datetime(now - timedelta(days=int(days)))

    return CaseES().domain(domain).modified_range(lt=then).is_closed(False).count()


def forms(domain, *args):
    return get_number_of_forms_in_domain(domain)


def forms_in_last(domain, days):
    """
    Returns the number of forms submitted in the last given number of days
    """
    then = datetime.utcnow() - timedelta(days=int(days))
    return FormES().domain(domain).submitted(gte=then).count()


def get_sms_count(domain, direction=None, days=None):
    """
    :param domain: domain name
    :param direction: can specify INCOMING or OUTGOING, or None to retrieve both
    :param days: only return count of sms docs from the past N days
    :return: number of sms docs fetched based on query parameters specified
    """
    assert direction in (INCOMING, OUTGOING, None), repr(direction)
    query = SMSES().domain(domain).size(0)

    if direction == INCOMING:
        query = query.incoming_messages()
    elif direction == OUTGOING:
        query = query.outgoing_messages()

    if days:
        days = int(days) if isinstance(days, str) else days
        query = query.received(date.today() - relativedelta(days=days))

    return query.run().total


def sms(domain, direction):
    return get_sms_count(domain, direction=direction)


def sms_in_last(domain, days=None):
    return get_sms_count(domain, days=days)


def sms_in_last_bool(domain, days=None):
    return sms_in_last(domain, days) > 0


def sms_in_in_last(domain, days=None):
    return get_sms_count(domain, direction=INCOMING, days=days)


def sms_out_in_last(domain, days=None):
    return get_sms_count(domain, direction=OUTGOING, days=days)


def active(domain, *args):
    return domain_has_submission_in_last_30_days(domain)


def display_time(submission_time, display=True):
    if display:
        return submission_time.strftime(DISPLAY_DATE_FORMAT)
    else:
        return json_format_datetime(submission_time)


def first_domain_for_user(domain):
    domain_obj = Domain.get_by_name(domain)
    if domain_obj:
        return domain_obj.first_domain_for_user
    return None


def first_form_submission(domain, display=True):
    try:
        submission_time = get_first_form_submission_received(domain)
    except ValueError:
        return None
    return display_time(submission_time, display) if submission_time else None


def last_form_submission(domain, display=True):
    try:
        submission_time = get_last_form_submission_received(domain)
    except ValueError:
        return None
    return display_time(submission_time, display) if submission_time else None


def get_300th_form_submission_received(domain):
    result = FormES().domain(domain).start(300).size(1).sort('received_on').fields(['received_on']).run().hits
    if not result:
        return

    return iso_string_to_datetime(result[0]['received_on'])


def has_app(domain, *args):
    return domain_has_apps(domain)


def _get_domain_apps(domain):
    return Domain.get_by_name(domain).applications()


def app_list(domain, *args):
    apps = _get_domain_apps(domain)
    return render_to_string("domain/partials/app_list.html", {"apps": apps, "domain": domain})


def uses_reminders(domain, *args):
    return domain_has_reminders(domain)


def not_implemented(domain, *args):
    return '<p class="text-danger">not implemented</p>'

CALC_ORDER = [
    'num_web_users', 'num_mobile_users', 'forms', 'cases',
    'active_mobile_users', 'inactive_mobile_users', 'active_mobile_users--365',
    'active_cases', 'cases_in_last--30', 'cases_in_last--60',
    'cases_in_last--90', 'cases_in_last--120', 'active',
    'first_form_submission', 'last_form_submission', 'has_app', 'web_users',
    'active_apps', 'uses_reminders', 'sms--I', 'sms--O', 'sms_in_last',
    'sms_in_last--30', 'sms_in_last_bool', 'sms_in_last_bool--30',
    'sms_in_in_last--30', 'sms_out_in_last--30',
]

CALCS = {
    'num_web_users': "# web users",
    'num_mobile_users': "# mobile users",
    'forms': "# forms",
    'sms--I': "# incoming SMS",
    'sms--O': "# outgoing SMS",
    'sms_in_last--30': "# SMS in last 30 days",
    'sms_in_last': "# SMS ever",
    'sms_in_last_bool--30': "used messaging in last 30 days",
    'sms_in_last_bool': "used messaging ever",
    'sms_in_in_last--30': "# incoming SMS in last 30 days",
    'sms_out_in_last--30': "# outgoing SMS in last 30 days",
    'cases': "# cases",
    'active_mobile_users': "# active mobile users in last 30 days",
    'inactive_mobile_users': "# inactive mobile users in last 30 days",
    'active_mobile_users--365': "# active mobile users in last 365 days",
    'active_cases': "# active cases",
    'cases_in_last--30': "# cases seen last 30 days",
    'cases_in_last--60': "# cases seen last 60 days",
    'cases_in_last--90': "# cases seen last 90 days",
    'cases_in_last--120': "# cases seen last 120 days",
    'active': "Active",
    'first_form_submission': "Date of first form submission",
    'last_form_submission': "Date of last form submission",
    'has_app': "Has App",
    'web_users': "list of web users",
    'active_apps': "list of active apps",
    'uses_reminders': "uses reminders",
}

CALC_FNS = {
    'num_web_users': num_web_users,
    "num_mobile_users": num_mobile_users,
    "first_domain_for_user": first_domain_for_user,
    "forms": forms,
    "forms_in_last": forms_in_last,
    "sms": sms,
    "sms_in_last": sms_in_last,
    "sms_in_last_bool": sms_in_last_bool,
    "sms_in_in_last": sms_in_in_last,
    "sms_out_in_last": sms_out_in_last,
    "cases": cases,
    "active_mobile_users": active_mobile_users,
    "inactive_mobile_users": inactive_mobile_users,
    "active_cases": not_implemented,
    "cases_in_last": cases_in_last,
    "inactive_cases_in_last": inactive_cases_in_last,
    "active": active,
    "first_form_submission": first_form_submission,
    "last_form_submission": last_form_submission,
    "has_app": has_app,
    "web_users": not_implemented,
    "active_apps": app_list,
    'uses_reminders': uses_reminders,
    '300th_form_submission': get_300th_form_submission_received
}


def dom_calc(calc_tag, dom, extra_arg=''):
    ans = CALC_FNS[calc_tag](dom, extra_arg) if extra_arg else CALC_FNS[calc_tag](dom)
    if ans is True:
        return _('yes')
    elif ans is False:
        return _('no')
    return ans


@quickcache([], timeout=23 * 60 * 60)
def all_domain_stats():
    webuser_counts = defaultdict(int)
    commcare_counts = defaultdict(int)

    for row in CouchUser.get_db().view('users/by_domain', startkey=["active"],
                                       endkey=["active", {}], group_level=3).all():
        _, domain, doc_type = row['key']
        value = row['value']
        {
            'WebUser': webuser_counts,
            'CommCareUser': commcare_counts
        }[doc_type][domain] = value

    return {
        "web_users": webuser_counts,
        "commcare_users": commcare_counts,
    }


def calced_props(domain_obj, id, all_stats):
    dom = domain_obj.name
    return {
        "_id": id,
        "cp_n_web_users": int(all_stats["web_users"].get(dom, 0)),
        "cp_n_active_cc_users": int(CALC_FNS["active_mobile_users"](dom)),
        "cp_n_active_cc_users_365_days": int(CALC_FNS["active_mobile_users"](dom, 365)),
        "cp_n_cc_users": int(all_stats["commcare_users"].get(dom, 0)),
        "cp_n_active_cases": int(CALC_FNS["cases_in_last"](dom, 120)),
        "cp_n_users_submitted_form": total_distinct_users(dom),
        "cp_n_inactive_cases": int(CALC_FNS["inactive_cases_in_last"](dom, 120)),
        "cp_n_30_day_cases": int(CALC_FNS["cases_in_last"](dom, 30)),
        "cp_n_60_day_cases": int(CALC_FNS["cases_in_last"](dom, 60)),
        "cp_n_90_day_cases": int(CALC_FNS["cases_in_last"](dom, 90)),
        "cp_n_cases": int(CALC_FNS["cases"](dom)),
        "cp_n_forms": int(CALC_FNS["forms"](dom)),
        "cp_n_forms_30_d": int(CALC_FNS["forms_in_last"](dom, 30)),
        "cp_n_forms_60_d": int(CALC_FNS["forms_in_last"](dom, 60)),
        "cp_n_forms_90_d": int(CALC_FNS["forms_in_last"](dom, 90)),
        "cp_first_domain_for_user": CALC_FNS["first_domain_for_user"](dom),
        "cp_first_form": CALC_FNS["first_form_submission"](dom, False),
        "cp_last_form": CALC_FNS["last_form_submission"](dom, False),
        "cp_is_active": CALC_FNS["active"](dom),
        "cp_has_app": CALC_FNS["has_app"](dom),
        "cp_last_updated": json_format_datetime(datetime.utcnow()),
        "cp_n_in_sms": int(CALC_FNS["sms"](dom, INCOMING)),
        "cp_n_out_sms": int(CALC_FNS["sms"](dom, OUTGOING)),
        "cp_n_sms_ever": int(CALC_FNS["sms_in_last"](dom)),
        "cp_n_sms_30_d": int(CALC_FNS["sms_in_last"](dom, 30)),
        "cp_n_sms_60_d": int(CALC_FNS["sms_in_last"](dom, 60)),
        "cp_n_sms_90_d": int(CALC_FNS["sms_in_last"](dom, 90)),
        "cp_sms_ever": CALC_FNS["sms_in_last_bool"](dom),
        "cp_sms_30_d": CALC_FNS["sms_in_last_bool"](dom, 30),
        "cp_n_sms_in_30_d": int(CALC_FNS["sms_in_in_last"](dom, 30)),
        "cp_n_sms_in_60_d": int(CALC_FNS["sms_in_in_last"](dom, 60)),
        "cp_n_sms_in_90_d": int(CALC_FNS["sms_in_in_last"](dom, 90)),
        "cp_n_sms_out_30_d": int(CALC_FNS["sms_out_in_last"](dom, 30)),
        "cp_n_sms_out_60_d": int(CALC_FNS["sms_out_in_last"](dom, 60)),
        "cp_n_sms_out_90_d": int(CALC_FNS["sms_out_in_last"](dom, 90)),
        "cp_300th_form": CALC_FNS["300th_form_submission"](dom),
        "cp_n_30_day_user_cases": cases_in_last(dom, 30, case_type="commcare-user"),
        "cp_n_trivet_backends": num_telerivet_backends(dom),
        "cp_use_domain_security": use_domain_security_settings(domain_obj),
        "cp_n_custom_roles": num_custom_roles(dom),
        "cp_using_locations": users_have_locations(dom),
        "cp_n_loc_restricted_roles": num_location_restricted_roles(dom),
        "cp_n_case_sharing_olevels": num_case_sharing_loc_types(dom),
        "cp_n_case_sharing_groups": num_case_sharing_groups(dom),
        "cp_n_repeaters": num_repeaters(dom),
        "cp_n_case_exports": num_exports(dom),
        "cp_n_deid_exports": num_deid_exports(dom),
        "cp_n_saved_exports": num_saved_exports(dom),
        "cp_n_rb_reports": number_of_report_builder_reports(dom),
        "cp_n_ucr_reports": number_of_ucr_reports(dom),
        "cp_n_lookup_tables": num_lookup_tables(dom),
        "cp_has_project_icon": has_domain_icon(domain_obj),
        "cp_n_apps_with_icon": num_apps_with_icon(dom),
        "cp_n_apps": len(_get_domain_apps(dom)),
        "cp_n_apps_with_multi_lang": num_apps_with_multi_languages(dom),
        "cp_n_saved_custom_exports": get_export_count_by_domain(dom),
    }


def total_distinct_users(domain):
    """
    Get total number of users who've ever submitted a form in a domain.
    """
    query = FormES().domain(domain).user_aggregation()
    terms = {
        user_id for user_id in query.run().aggregations.user.keys
        if user_id not in WEIRD_USER_IDS
    }
    user_ids = terms.intersection(set(CouchUser.ids_by_domain(domain)))
    return len(user_ids)


def num_telerivet_backends(domain):
    from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
    backends = SQLMobileBackend.get_domain_backends(SQLMobileBackend.SMS, domain)
    return len([b for b in backends if isinstance(b, SQLTelerivetBackend)])


def use_domain_security_settings(domain_obj):
    return any([
        getattr(domain_obj, attr, False)
        for attr in ['two_factor_auth', 'secure_sessions', 'strong_mobile_passwords']
    ])


def num_custom_roles(domain):
    return len(get_custom_roles_for_domain(domain))


def num_location_restricted_roles(domain):
    roles = [r for r in UserRole.objects.get_by_domain(domain)
             if not r.permissions.access_all_locations]
    return len(roles)


def num_case_sharing_loc_types(domain):
    loc_types = [l for l in LocationType.objects.by_domain(domain) if l.shares_cases]
    return len(loc_types)


def num_case_sharing_groups(domain):
    groups = [g for g in Group.by_domain(domain) if g.case_sharing]
    return len(groups)


def num_repeaters(domain):
    return Repeater.objects.filter(domain=domain).count()


def _get_domain_exports(domain):
    return get_form_exports_by_domain(domain) + get_case_exports_by_domain(domain)


def num_deid_exports(domain):
    return len([e for e in _get_domain_exports(domain) if e.is_safe])


def num_exports(domain):
    return len(_get_domain_exports(domain))


def num_saved_exports(domain):
    return len([e for e in _get_domain_exports(domain)
                if hasattr(e, "is_daily_saved_export") and e.is_daily_saved_export])


def num_lookup_tables(domain):
    return LookupTable.objects.by_domain(domain).count()


def has_domain_icon(domain_obj):
    return domain_obj.has_custom_logo


def num_apps_with_icon(domain):
    apps = _get_domain_apps(domain)
    return len([a for a in apps if isinstance(a, ApplicationMediaMixin) and a.logo_refs])


def num_apps_with_profile(domain):
    apps = _get_domain_apps(domain)
    return len([a for a in apps if a.build_profiles])


def num_apps_with_multi_languages(domain):
    apps = _get_domain_apps(domain)
    return len([a for a in apps if len(a.langs) > 1])
