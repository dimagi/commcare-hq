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
