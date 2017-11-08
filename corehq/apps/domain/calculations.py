from __future__ import absolute_import
from collections import defaultdict
from corehq.apps.hqcase.analytics import get_number_of_cases_in_domain
from corehq.apps.users.dbaccessors.all_commcare_users import get_web_user_count, get_mobile_user_count
from corehq.util.dates import iso_string_to_datetime
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.dbaccessors import domain_has_apps
from corehq.apps.users.util import WEIRD_USER_IDS
from corehq.apps.es.sms import SMSES
from corehq.apps.es.forms import FormES
from corehq.apps.hqadmin.reporting.reports import (
    get_mobile_users,
)
from couchforms.analytics import get_number_of_forms_in_domain, \
    domain_has_submission_in_last_30_days, get_first_form_submission_received, \
    get_last_form_submission_received

from corehq.apps.domain.models import Domain
from corehq.apps.reminders.models import CaseReminderHandler
from corehq.apps.users.models import CouchUser
from corehq.elastic import es_query, ADD_TO_ES_FILTER
from dimagi.utils.parsing import json_format_datetime


def num_web_users(domain, *args):
    return get_web_user_count(domain, include_inactive=False)


def num_mobile_users(domain, *args):
    return get_mobile_user_count(domain, include_inactive=False)


DISPLAY_DATE_FORMAT = '%Y/%m/%d %H:%M:%S'


def active_mobile_users(domain, *args):
    """
    Returns the number of mobile users who have submitted a form or SMS in the
    last 30 days
    """
    now = datetime.utcnow()
    then = (now - timedelta(days=30))

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
    return num_users if 'inactive' not in args else len(user_ids) - num_users


def cases(domain, *args):
    return get_number_of_cases_in_domain(domain)


def cases_in_last(domain, days):
    """
    Returns the number of open cases that have been modified in the last <days> days
    """
    now = datetime.utcnow()
    then = json_format_datetime(now - timedelta(days=int(days)))
    now = json_format_datetime(now)

    q = {"query": {
        "range": {
            "modified_on": {
                "from": then,
                "to": now}}}}
    data = es_query(params={"domain.exact": domain, 'closed': False}, q=q, es_index='cases', size=1)
    return data['hits']['total'] if data.get('hits') else 0


def inactive_cases_in_last(domain, days):
    """
    Returns the number of open cases that have been modified in the last <days> days
    """
    now = datetime.utcnow()
    then = json_format_datetime(now - timedelta(days=int(days)))
    now = json_format_datetime(now)

    q = {"query":
             {"bool": {
                 "must_not": {
                     "range": {
                         "modified_on": {
                             "from": then,
                             "to": now }}}}}}
    data = es_query(params={"domain.exact": domain, 'closed': False}, q=q, es_index='cases', size=1)
    return data['hits']['total'] if data.get('hits') else 0


def forms(domain, *args):
    return get_number_of_forms_in_domain(domain)


def forms_in_last(domain, days):
    """
    Returns the number of forms submitted in the last given number of days
    """
    then = datetime.utcnow() - timedelta(days=int(days))
    return FormES().domain(domain).submitted(gte=then).size(0).run().total


def j2me_forms_in_last(domain, days):
    """
    Returns the number of forms submitted by j2me in the last given number of days
    """
    then = datetime.utcnow() - timedelta(days=int(days))
    return FormES().domain(domain).j2me_submissions(gte=then).size(0).run().total


def j2me_forms_in_last_bool(domain, days):
    return j2me_forms_in_last(domain, days) > 0


def _sms_helper(domain, direction=None, days=None):
    query = SMSES().domain(domain).size(0)

    if direction:
        query = query.direction(direction)

    if days:
        query = query.received(date.today() - relativedelta(days=30))

    return query.run().total


def sms(domain, direction):
    return _sms_helper(domain, direction=direction)


def sms_in_last(domain, days=None):
    return _sms_helper(domain, days=days)


def sms_in_last_bool(domain, days=None):
    return sms_in_last(domain, days) > 0


def sms_in_in_last(domain, days=None):
    return _sms_helper(domain, direction="I", days=days)


def sms_out_in_last(domain, days=None):
    return _sms_helper(domain, direction="O", days=days)


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


def app_list(domain, *args):
    domain = Domain.get_by_name(domain)
    apps = domain.applications()
    return render_to_string("domain/partials/app_list.html", {"apps": apps, "domain": domain.name})


def uses_reminders(domain, *args):
    handlers = CaseReminderHandler.get_handlers(domain)
    return len(handlers) > 0


def not_implemented(domain, *args):
    return '<p class="text-danger">not implemented</p>'

CALC_ORDER = [
    'num_web_users', 'num_mobile_users', 'forms', 'cases',
    'mobile_users--active', 'mobile_users--inactive', 'active_cases',
    'cases_in_last--30', 'cases_in_last--60', 'cases_in_last--90',
    'cases_in_last--120', 'active', 'first_form_submission',
    'last_form_submission', 'has_app', 'web_users', 'active_apps',
    'uses_reminders', 'sms--I', 'sms--O', 'sms_in_last', 'sms_in_last--30',
    'sms_in_last_bool', 'sms_in_last_bool--30', 'sms_in_in_last--30',
    'sms_out_in_last--30', 'j2me_forms_in_last--30', 'j2me_forms_in_last--60',
    'j2me_forms_in_last--90', 'j2me_forms_in_last_bool--90',
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
    'mobile_users--active': "# active mobile users",
    'mobile_users--inactive': "# inactive mobile users",
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
    'j2me_forms_in_last--30': "# j2me forms in last 30 days",
    'j2me_forms_in_last--60': "# j2me forms in last 60 days",
    'j2me_forms_in_last--90': "# j2me forms in last 90 days",
    'j2me_forms_in_last_bool--90': "j2me forms in last 90 days",
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
    "mobile_users": active_mobile_users,
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
    'j2me_forms_in_last': j2me_forms_in_last,
    'j2me_forms_in_last_bool': j2me_forms_in_last_bool,
    '300th_form_submission': get_300th_form_submission_received
}


def dom_calc(calc_tag, dom, extra_arg=''):
    ans = CALC_FNS[calc_tag](dom, extra_arg) if extra_arg else CALC_FNS[calc_tag](dom)
    if ans is True:
        return _('yes')
    elif ans is False:
        return _('no')
    return ans


def all_domain_stats():
    webuser_counts = defaultdict(lambda: 0)
    commcare_counts = defaultdict(lambda: 0)

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


def calced_props(dom, id, all_stats):
    return {
        "_id": id,
        "cp_n_web_users": int(all_stats["web_users"].get(dom, 0)),
        "cp_n_active_cc_users": int(CALC_FNS["mobile_users"](dom)),
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
        "cp_n_in_sms": int(CALC_FNS["sms"](dom, "I")),
        "cp_n_out_sms": int(CALC_FNS["sms"](dom, "O")),
        "cp_n_sms_ever": int(CALC_FNS["sms_in_last"](dom)),
        "cp_n_sms_30_d": int(CALC_FNS["sms_in_last"](dom, 30)),
        "cp_n_sms_60_d": int(CALC_FNS["sms_in_last"](dom, 60)),
        "cp_n_sms_90_d": int(CALC_FNS["sms_in_last"](dom, 90)),
        "cp_sms_ever": int(CALC_FNS["sms_in_last_bool"](dom)),
        "cp_sms_30_d": int(CALC_FNS["sms_in_last_bool"](dom, 30)),
        "cp_n_sms_in_30_d": int(CALC_FNS["sms_in_in_last"](dom, 30)),
        "cp_n_sms_in_60_d": int(CALC_FNS["sms_in_in_last"](dom, 60)),
        "cp_n_sms_in_90_d": int(CALC_FNS["sms_in_in_last"](dom, 90)),
        "cp_n_sms_out_30_d": int(CALC_FNS["sms_out_in_last"](dom, 30)),
        "cp_n_sms_out_60_d": int(CALC_FNS["sms_out_in_last"](dom, 60)),
        "cp_n_sms_out_90_d": int(CALC_FNS["sms_out_in_last"](dom, 90)),
        "cp_n_j2me_30_d": int(CALC_FNS["j2me_forms_in_last"](dom, 30)),
        "cp_n_j2me_60_d": int(CALC_FNS["j2me_forms_in_last"](dom, 60)),
        "cp_n_j2me_90_d": int(CALC_FNS["j2me_forms_in_last"](dom, 90)),
        "cp_j2me_90_d_bool": int(CALC_FNS["j2me_forms_in_last_bool"](dom, 90)),
        "cp_300th_form": CALC_FNS["300th_form_submission"](dom)
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
