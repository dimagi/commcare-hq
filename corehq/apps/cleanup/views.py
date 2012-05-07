from collections import defaultdict
from corehq.apps.domain.decorators import require_superuser
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.make_uuid import random_hex
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
import json
from django.views.decorators.http import require_POST
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions, CommCareUser
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.web import render_to_response, json_request, json_response
from corehq.apps.receiverwrapper.util import get_submit_url

require_can_cleanup = require_permission(Permissions.EDIT_DATA)


# -----------submissions-------------

@require_can_cleanup
def submissions(request, domain, template="cleanup/submissions.html"):
    return render_to_response(request, template, {'domain': domain})

@require_can_cleanup
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
                ).one()
                total = total['value'] if total else 0
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
                ).one()
                total = total['value'] if total else 0
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

@require_can_cleanup
def users_json(request, domain):
    users = CommCareUser.by_domain(domain)
    users = [{"username": user.username, "userID": user.user_id} for user in users]
    return json_response(users)

@require_POST
@require_can_cleanup
def relabel_submissions(request, domain):
    userID = request.POST['userID']
    data = json.loads(request.POST['data'])
    group = data['group']
    keys = data['submissions']
    xforms = []
    if group:
        xforms = _get_submissions(domain, keys)
    cases = _get_cases(xforms)

    # Oh, yeah, here we go baby!
    for xform in xforms:
        xform.form['meta']['userID'] = userID
        xform.save()
    for case in cases:
        case.user_id = userID
        case.save()

    
    return HttpResponseRedirect(reverse('corehq.apps.cleanup.views.submissions', args=[domain]))

# -----------cases-------------

@require_can_cleanup
def cases(request, domain, template="cleanup/cases.html"):
    return render_to_response(request, template, {'domain': domain})

@require_can_cleanup 
def cases_json(request, domain):
    def query(stale="ok", **kwargs):
        subs = [dict(
            userID      = r['key'][1],
            username    = r['key'][2],
            deviceID    = r['key'][3],
            submissions = r['value']['count'],
            start       = r['value']['start'].split('T')[0],
            end         = r['value']['end'  ].split('T')[0]
        ) for r in get_db().view('cleanup/case_submissions',
             startkey=[domain],
             endkey=[domain, {}],
             group=True,
#             stale=stale
        )]
        subs.sort(key=lambda sub: (sub['userID'], sub['end']))

        # Try and help identify lost devices
        latest_start = defaultdict(lambda: None)
        for sub in subs:
            latest_start[sub['userID']] = max(sub['start'], latest_start[sub['userID']])
        for sub in subs:
            if sub['end'] < latest_start[sub['userID']]:
                sub['old'] = True
            else:
                sub['old'] = False


        # show the number of cases made by these xforms
#        for sub in subs:
#            cases = _get_cases(_get_submissions(domain, [sub]))
#            sub['cases'] = len([None for case in cases if not case.closed])

        open_cases = CommCareCase.view('hqcase/open_cases', startkey=[domain], endkey=[domain, {}], reduce=False, include_docs=True).all()
        xform_ids = [case.xform_ids[0] for case in open_cases]
        case_count = defaultdict(int)
        for xform_id in xform_ids:
            xform = XFormInstance.get(xform_id)
            meta = xform.form['meta']
            case_count[(meta['userID'], meta['username'], meta['deviceID'])] += 1
        for sub in subs:
            sub['cases'] = case_count[(sub['userID'], sub['username'], sub['deviceID'])]

        return json_response({
            "results": subs,
            "total": len(subs),
        })
    return query(**json_request(request.GET))

@require_can_cleanup 
@require_POST
def close_cases(request, domain):
    data = json.loads(request.POST['data'])
    keys = data['submissions']
    def actually_close_cases(cases):
        for case in cases:
            for referral in case.referrals:
                case.force_close_referral(get_submit_url(domain), referral)
            case.force_close(get_submit_url(domain))
    xforms = _get_submissions(domain, keys)
    cases = _get_cases(xforms)
    actually_close_cases(cases)
    return HttpResponseRedirect(reverse('corehq.apps.cleanup.views.cases', args=[domain]))

def _get_submissions(domain, keys):
    xforms = []
    for key in keys:
        for sub in XFormInstance.view('cleanup/submissions', reduce=False,
            key=[domain, key['userID'], key['username'], key['deviceID']],
            include_docs=True
        ).all():
            xforms.append(sub)
    return xforms

def _get_cases(xforms):
    cases = []
    for case in CommCareCase.view('case/by_xform_id', 
                                  keys=[xform.get_id for xform in xforms], 
                                  reduce=False, include_docs=True).all():
        cases.append(case)
    return cases

@require_can_cleanup
@require_POST
def change_submissions_app_id(request, domain):
    app_id = request.POST['app_id'] or None
    xmlns = request.POST['xmlns']
    new_app_id = request.POST['new_app_id']
    next = request.POST['next']

    submissions = XFormInstance.view('reports/forms_by_xmlns',
        key=['^XFormInstance', domain, app_id, xmlns],
        include_docs=True,
        reduce=False,
    ).all()

    for sub in submissions:
        assert(getattr(sub, 'app_id', None) == app_id)
        assert(sub.xmlns == xmlns)
        sub.app_id = new_app_id
        sub.save()
    messages.success(request, 'Your fix was successful and affected %s submissions' % len(submissions))
    return HttpResponseRedirect(next)

@require_superuser
@require_POST
def delete_all_data(request, domain):
    xforms = XFormInstance.view('reports/all_submissions',
        startkey=[domain],
        endkey=[domain, {}]
    )
    cases = CommCareCase.view('case/by_date_modified',
        startkey=[domain, {}, {}],
        endkey=[domain, {}, {}, {}],
    )
    suffix = DELETED_SUFFIX
    deletion_id = random_hex()
    for thing_list in (xforms, cases):
        for thing in thing_list:
            thing.doc_type += suffix
            thing['-deletion_id'] = deletion_id
            thing.save()