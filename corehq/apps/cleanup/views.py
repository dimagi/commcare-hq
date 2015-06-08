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
