from _collections import defaultdict
from collections import namedtuple
from datetime import datetime, timedelta
import json
from django.http import Http404, HttpResponse
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reports.views import user_id_to_username
from corehq.apps.users.models import CouchUser
from couchforms.models import XFormInstance
from dimagi.utils.parsing import string_to_datetime, json_format_datetime

DOMAIN = "dodoma"

@login_and_domain_required
def household_verification_json(request, domain):
    XMLNS = 'http://openrosa.org/formdesigner/9DAACA82-A414-499A-9C40-BC43775CEE79'
    if domain != DOMAIN:
        raise Http404
    last_hvid_path = json.loads(request.GET.get('household_verification', '["household_verification"]'))
    next_hvid_path = json.loads(request.GET.get('household_follow_id', '["household_follow_id"]'))
    xmlns = json.loads(request.GET.get('xmlns', "null")) or XMLNS
    range = json.loads(request.GET.get('range', 'null'))

    if range:
        start, end = map(string_to_datetime, range)
    else:
        now = datetime.utcnow()
        start, end = now - timedelta(days=7), now


    submissions = XFormInstance.view('reports/submissions_by_domain_xmlns',
        reduce=False,
        startkey=[domain, xmlns, json_format_datetime(start)],
        endkey=[domain, xmlns, json_format_datetime(end)],
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
        s['username'] = None
    users = CouchUser.commcare_users_by_domain(domain)

    for user in users:
        cc_account = user.default_commcare_account
        userID = cc_account.login_id
        username = user_id_to_username(userID)
        print userID, username
        if userID in stats_by_userID:
            stats_by_userID[userID]['username'] = username
        else:
            stats.append({'userID': userID, 'username': username, 'total': 0, 'correct': 0})
    stats.sort(key=lambda s: s['username'])

    
    return HttpResponse(json.dumps(stats))

HVSub = namedtuple("HVSub", "userID  caseID  time  next_hvid  last_hvid")

def get_household_verification_data(submissions, next_hvid_path, last_hvid_path):
    submissions = map(lambda s: HVSub(
        userID      = s['form']['meta']['userID'],
        caseID      = s['form']['case']['case_id'],
        time        = s['received_on'],
        next_hvid   = reduce(dict.__getitem__, next_hvid_path, s['form']),
        last_hvid   = reduce(dict.__getitem__, last_hvid_path, s['form']),
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