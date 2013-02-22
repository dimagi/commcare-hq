from dimagi.utils.couch.database import get_db

CALCS = {
    'mobile_users': "# mobile users",
    'cases': "# cases",
    'active_mobile_users': "# active mobile users",
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

def web_users(domain, *args):
    key = ["active", domain, 'WebUser']
    row = get_db().view('users/by_domain', startkey=key, endkey=key+[{}]).first()
    return {"value": row["value"] if row else 0}

def mobile_users(domain, *args):
    key = ["active", domain, 'CommCareUser']
    row = get_db().view('users/by_domain', startkey=key, endkey=key+[{}]).first()
    return {"value": row["value"] if row else 0}

def ppass(domain, *args):
    return {"value": "not implemented"}

CALC_FNS = {
    "mobile_users": mobile_users,
    "cases": ppass,
    "active_mobile_users": ppass,
    "active_cases": ppass,
    "cases_in_last": ppass,
    "active": ppass,
    "first_form_submission": ppass,
    "last_form_submission": ppass,
    "has_app": ppass,
    "web_users": web_users,
    "active_apps": ppass,
}
