from _collections import defaultdict
from collections import namedtuple
from datetime import datetime, timedelta
import json
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponse
from django.shortcuts import render

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reports.util import make_form_couch_key
from corehq.apps.users.models import CouchUser, CommCareUser
from couchforms.models import XFormInstance
from dimagi.utils.parsing import string_to_datetime, json_format_datetime
from corehq.apps.users.util import user_id_to_username

DOMAIN = "dodoma"

def call_as_view(fn, GET, **kwargs):
    request_kwargs = dict([(str(key), json.loads(val)) for key, val in GET.items()])
    request_kwargs.update(kwargs)
    return fn(**request_kwargs)

def viewify(fn, GET, **kwargs):
    return HttpResponse(json.dumps(
        call_as_view(fn, GET, **kwargs)
    ))

@login_and_domain_required
def household_verification(request, domain):
    if domain != DOMAIN:
        raise Http404
    report = call_as_view(_household_verification_json, request.GET, domain=domain)
    report['name'] = "Household Verification"
    return render(request, 'reports/async/tabular.html', {
        "domain": domain,
        "report": report,
        "report_base": "reports/base_template.html"
    })

@login_and_domain_required
def household_verification_json(request, domain):
    if domain != DOMAIN:
        raise Http404
    return viewify(_household_verification_json, request.GET, domain=domain)

def _household_verification_json(
    domain="dodoma",
    last_hvid_path=["household_verification"],
    next_hvid_path=["followup_id"],
    xmlns='http://openrosa.org/formdesigner/9DAACA82-A414-499A-9C40-BC43775CEE79',
    range=None
):
    if range:
        start, end = map(string_to_datetime, range)
    else:
        now = datetime.utcnow()
        start, end = now - timedelta(days=7), now

    key = make_form_couch_key(domain, xmlns=xmlns)
    submissions = XFormInstance.view('reports_forms/all_forms',
        reduce=False,
        startkey=key+[json_format_datetime(start)],
        endkey=key+[json_format_datetime(end)],
        include_docs=True,
    )

    stats = get_household_verification_data(
        submissions=submissions,
        next_hvid_path=next_hvid_path,
        last_hvid_path=last_hvid_path,
    )

    stats_by_userID = {}
    for s in stats:
        stats_by_userID[s['userID']] = s
        s['username'] = "*%s" % s['userID']
    users = CommCareUser.by_domain(domain)

    for user in users:
        userID = user.user_id
        username = user_id_to_username(userID)
        if userID in stats_by_userID:
            stats_by_userID[userID]['username'] = username
        else:
            stats.append({'userID': userID, 'username': username, 'total': 0, 'correct': 0})
    stats.sort(key=lambda s: s['username'])

    
    return {
        "headers": ["Username", "Correct", "Total", "Percent Correct"],
        "rows": [[
            s['username'],
            s['correct'],
            s['total'],
            ("%s%%" % int(s['correct']*100/s['total']) if s['total'] else "---")
        ] for s in stats],
    }

HVSub = namedtuple("HVSub", "userID  caseID  time  next_hvid  last_hvid")

def get_household_verification_data(submissions, next_hvid_path, last_hvid_path):

    def follow_path(d, path):
        try:
            return reduce(dict.__getitem__, path, d)
        except:
            return None

    submissions = map(lambda s: HVSub(
        userID      = s['form']['meta']['userID'],
        caseID      = s['form']['case']['case_id'],
        time        = s['received_on'],
        next_hvid   = follow_path(s['form'], next_hvid_path),
        last_hvid   = follow_path(s['form'], last_hvid_path),
    ), submissions)

    submissions.sort()

    # >>> state[userID][caseID]
    # {'last_hvid': "203", 'total': 10, 'correct': 9}
    state = defaultdict(
        lambda: defaultdict(
            lambda: {
                'last_hvid': None,
                'total': 0,
                'correct': 0
            }
        )
    )

    for s in submissions:
        last_hvid = state[s.userID][s.caseID]['last_hvid']
        if last_hvid is not None:
            state[s.userID][s.caseID]['total'] += 1
            if s.last_hvid == last_hvid:
                state[s.userID][s.caseID]['correct'] += 1
        state[s.userID][s.caseID]['last_hvid'] = s.next_hvid

    response = []
    for userID in state:
        response.append({
            'userID': userID,
            'total': sum([state[userID][caseID]['total'] for caseID in state[userID]]),
            'correct': sum([state[userID][caseID]['correct'] for caseID in state[userID]])
        })
    return response
