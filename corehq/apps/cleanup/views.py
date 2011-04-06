from django.http import HttpResponse
import json
from corehq.apps.users.util import format_username
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.web import render_to_response

def json_response(obj):
    return HttpResponse(json.dumps(obj))

def json_request(params):
    return dict([(str(key), json.loads(val)) for (key,val) in params.items()])

def submissions_json(request, domain):
    def query(limit=100, userID=None, group=False, username__exclude=["demo_user", "admin"], **kwargs):
        if group:
            if userID is None:
                key = [domain]
            else:
                key = [domain, userID]
            subs = [dict(
                userID = r['key'][1],
                username = r['key'][2],
                deviceID = r['key'][3],
                submissions = r['value'],
            ) for r in get_db().view('cleanup/submissions',
                startkey = key,
                endkey   = key + [{}],
                group    = True,
            )]
            total = len(subs)
        else:
            if userID is None:
                subs = XFormInstance.view('reports/all_submissions',
                    startkey=[domain, {}],
                    endkey=[domain],
                    reduce=False,
                    include_docs=True,
                    descending=True,
                    limit=limit
                )
                total = get_db().view('reports/all_submissions',
                    startkey=[domain],
                    endkey=[domain, {}],
                    group_level=1
                ).one()['value']
            else:
                subs = XFormInstance.view('reports/submit_history',
                    startkey=[domain, userID, {}],
                    endkey=[domain, userID],
                    reduce=False,
                    include_docs=True,
                    descending=True,
                    limit=limit
                )
                total = get_db().view('reports/submit_history',
                    startkey=[domain, userID],
                    endkey=[domain, userID, {}],
                    group_level=2
                ).one()['value']
            _subs = []
            for s in subs:
                try:
                    _subs.append(dict(
                        username = s['form']['meta']['username'],
                        userID = s['form']['meta']['userID'],
                        received_on = unicode(s['received_on']),
                        deviceID = s['form']['meta']['deviceID'],
                    ))
                except:
                    continue
            subs = _subs
        if username__exclude:
            username__exclude = set(username__exclude)
            subs = filter(lambda sub: sub['username'] not in username__exclude, subs)
        return json_response({
            "results": subs,
            "total": total,
        })
    return query(**json_request(request.GET))

def users_json(request, domain):
    users = [{"username": "danny", "userID": "alsdkfjalskdfj"}]
    return json_response(users)
def submissions(request, domain, template="cleanup/submissions.html"):
    return render_to_response(request, template, {'domain': domain})