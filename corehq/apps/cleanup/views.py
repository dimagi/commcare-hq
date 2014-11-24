from couchdbkit.exceptions import ResourceNotFound

from django.contrib import messages
from django.shortcuts import render
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_POST, require_GET
from corehq.apps.reports.util import make_form_couch_key

from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.make_uuid import random_hex
from dimagi.utils.couch.database import get_db
from dimagi.utils.web import json_response

from casexml.apps.case.models import CommCareCase

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.groups.models import Group
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CommCareUser, Permissions

from couchforms.models import XFormInstance

require_can_cleanup = require_permission(Permissions.edit_data)


@require_can_cleanup
@require_POST
def change_submissions_app_id(request, domain):
    app_id = request.POST['app_id'] or None
    xmlns = request.POST['xmlns']
    new_app_id = request.POST['new_app_id']
    next = request.POST['next']

    submissions = XFormInstance.view('exports_forms/by_xmlns',
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
def delete_all_data(request, domain, template="cleanup/delete_all_data.html"):
    if request.method == 'GET':
        return render(request, template, {
            'domain': domain
        })
    key = make_form_couch_key(domain)
    xforms = XFormInstance.view('reports_forms/all_forms',
        startkey=key,
        endkey=key+[{}],
        include_docs=True,
        reduce=False
    )
    cases = CommCareCase.view('case/by_date_modified_owner',
        startkey=[domain, {}, {}],
        endkey=[domain, {}, {}, {}],
        include_docs=True,
        reduce=False
    )
    suffix = DELETED_SUFFIX
    deletion_id = random_hex()
    for thing_list in (xforms, cases):
        for thing in thing_list:
            thing.doc_type += suffix
            thing['-deletion_id'] = deletion_id
            thing.save()
    return HttpResponseRedirect(reverse('homepage'))


# ----bihar migration----
@require_GET
@require_can_cleanup
def reassign_cases_to_correct_owner(request, domain, template='cleanup/reassign_cases_to_correct_owner.html'):
    log = {'unaffected': [], 'affected': [], 'unsure': []}
    @memoized
    def get_correct_group_id(user_id, group_id):
        group_ids = [group.get_id for group in Group.by_user(user_id) if group.case_sharing]
        if group_id in group_ids:
            return group_id
        else:
            try:
                g, = group_ids
                return g
            except ValueError:
                # too many values to unpack
                return None
    @memoized
    def get_meta(id):
        try:
            doc = get_db().get(id)
        except (ResourceNotFound, AttributeError):
            return {'name': None, 'doc_type': None}
        return {
            'name': {
                'CommCareUser': lambda user: CommCareUser.wrap(user).raw_username,
                'WebUser': lambda user: user['username'],
                'Group': lambda group: group['name']
            }.get(doc['doc_type'], lambda x: None)(doc),
            'doc_type': doc['doc_type']
        }

    for case in CommCareCase.get_all_cases(domain, include_docs=True):
        group_id = get_correct_group_id(case.user_id, case.owner_id)
        case_data = {
            'case': {'id': case.case_id, 'meta': {'name': case.name, 'doc_type': case.doc_type}, 'modified': case.modified_on},
            'user': {'id': case.user_id, 'meta': get_meta(case.user_id)},
            'owner': {'id': case.owner_id, 'meta': get_meta(case.owner_id)},
            'suggested': {'id': group_id, 'meta': get_meta(group_id)},
        }
        if group_id:
            if group_id != case.owner_id:
                log['affected'].append(case_data)

    if request.GET.get('ajax'):
        return json_response(log)
    else:
        return render(request, template, {
            'domain': domain,
            'results': log
        })
