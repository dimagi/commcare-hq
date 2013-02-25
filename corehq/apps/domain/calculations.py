from datetime import datetime, timedelta
from django.template.loader import render_to_string
from corehq.apps.domain.models import Domain
from corehq.apps.reports.util import make_form_couch_key
from dimagi.utils.couch.database import get_db

CALC_ORDER = [
    'num_web_users', 'num_mobile_users', 'forms', 'cases', 'mobile_users--active', 'mobile_users--inactive', 'active_cases', 'cases_in_last--30',
    'cases_in_last--60', 'cases_in_last--90', 'cases_in_last--120', 'active', 'first_form_submission',
    'last_form_submission', 'has_app', 'web_users', 'active_apps'
]

CALCS = {
    'num_web_users': "# web users",
    'num_mobile_users': "# mobile users",
    'forms': "# forms",
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
}

def num_web_users(domain, *args):
    key = ["active", domain, 'WebUser']
    row = get_db().view('users/by_domain', startkey=key, endkey=key+[{}]).one()
    return {"value": row["value"] if row else 0}

def num_mobile_users(domain, *args):
    row = get_db().view('users/by_domain', startkey=[domain], endkey=[domain, {}]).one()
    return {"value": row["value"] if row else 0}

def mobile_users(domain, active):
    key = ["active" if active == "active" else "inactive", domain, 'CommCareUser']
    row = get_db().view('users/by_domain', startkey=key, endkey=key+[{}]).one()
    return {"value": row["value"] if row else 0}

def cases(domain, *args):
    row = get_db().view("hqcase/types_by_domain", startkey=[domain], endkey=[domain, {}]).one()
    return {"value": row["value"] if row else 0}

DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

def cases_in_last(domain, days):
    now = datetime.now()
    then = (now - timedelta(days=int(days))).strftime(DATE_FORMAT)
    now = now.strftime(DATE_FORMAT)

    row = get_db().view("hqcase/all_cases", startkey=[domain, {}, {}, then], endkey=[domain, {}, {}, now]).one()
    return {"value": row["value"] if row else 0}

def forms(domain, *args):
    key = make_form_couch_key(domain)
    row = get_db().view("reports_forms/all_forms", startkey=key, endkey=key+[{}]).one()
    return {"value": row["value"] if row else 0}

def active(domain, *args):
    now = datetime.now()
    then = (now - timedelta(days=30)).strftime(DATE_FORMAT)
    now = now.strftime(DATE_FORMAT)

    key = ['submission', domain]
    row = get_db().view("hqcase/all_cases", startkey=key+[then], endkey=key+[now]).all()
    return {"value": 'yes' if row else 'no'}

def first_form_submission(domain, *args):
    key = make_form_couch_key(domain)
    row = get_db().view("reports_forms/all_forms", reduce=False, startkey=key, endkey=key+[{}]).first()
    return {"value": row["value"]["submission_time"] if row else "No submissions"}

def last_form_submission(domain, *args):
    key = make_form_couch_key(domain)
    row = get_db().view("reports_forms/all_forms", reduce=False, startkey=key, endkey=key+[{}]).all()[-1]
    return {"value": row["value"]["submission_time"] if row else "No submissions"}

def has_app(domain, *args):
    domain = Domain.get_by_name(domain)
    apps = domain.applications()
    return {"value": 'yes' if len(apps) > 0 else 'no'}

def app_list(domain, *args):
    domain = Domain.get_by_name(domain)
    apps = domain.applications()
    return {"value": render_to_string("domain/partials/app_list.html", {"apps": apps, "domain": domain.name})}

def not_implemented(domain, *args):
    return {"value": '<p class="text-error">not implemented</p>'}

CALC_FNS = {
    'num_web_users': num_web_users,
    "num_mobile_users": num_mobile_users,
    "forms": forms,
    "cases": cases,
    "mobile_users": mobile_users,
    "active_cases": not_implemented,
    "cases_in_last": cases_in_last,
    "active": active,
    "first_form_submission": first_form_submission,
    "last_form_submission": last_form_submission,
    "has_app": has_app,
    "web_users": not_implemented,
    "active_apps": app_list,
}
