# stub views file
from collections import defaultdict
from copy import deepcopy
import json
import uuid
import datetime
from casexml.apps.case import const
from casexml.apps.phone.xml import get_case_xml
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper.util import get_submit_url
from corehq.apps.users.models import CommCareUser
from dimagi.utils.parsing import json_format_datetime
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render

from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.decorators import login_and_domain_required, require_superuser
from corehq.apps.users.util import user_id_to_username
from django.template.loader import render_to_string
from receiver.util import spoof_submission

@login_and_domain_required
def open_cases_json(request, domain):
    delete_ids = json.loads(request.GET.get('delete_ids', 'false'))
    delete_doc_types = json.loads(request.GET.get('delete_doc_types', 'true'))
    username = request.GET.get("username", None)

    cases = CommCareCase.view('hqcase/open_cases', startkey=[domain], endkey=[domain, {}], reduce=False, include_docs=True)

    user_id_to_type_to_cases = defaultdict(lambda:defaultdict(list))
    for case in cases:
        case_json = deepcopy(case.to_json())
        user_id_to_type_to_cases[case.user_id][case.type].append(case_json)
        del case_json['domain']

        if delete_ids:
            del case_json['_id']
            del case_json['_rev']
            del case_json['user_id']
#            del case_json['type']
            del case_json['doc_type']
            case_json['actions'] = [action.action_type for action in case.actions]
            case_json['referrals'] = [referral.type for referral in case.referrals]

    usercases = [{
        "username": user_id_to_username(user_id),
        "cases": [{"type": type, "cases":cases} for (type, cases) in type_to_cases.items()]
    } for (user_id, type_to_cases) in user_id_to_type_to_cases.items()]
    usercases.sort(key=lambda x: x['username'])
    return HttpResponse(json.dumps(usercases))

@login_and_domain_required
def open_cases(request, domain, template="hqcase/open_cases.html"):
    return render(request, template, {"domain": domain})

@require_superuser
def explode_cases(request, domain, template="hqcase/explode_cases.html"):
    if request.method == 'POST':
        user_id = request.POST['user_id']
        user = CommCareUser.get_by_user_id(user_id, domain)
        factor = request.POST.get('factor', '2')
        try:
            factor = int(factor)
        except ValueError:
            messages.error(request, 'factor must be an int; was: %s' % factor)
        else:
            keys = [[domain, owner_id, False] for owner_id in user.get_owner_ids()]
            for case in CommCareCase.view('hqcase/by_owner',
                keys=keys,
                include_docs=True,
                reduce=False
            ):
                # we'll be screwing with this guy, so make him unsaveable
                case.save = None
                for i in range(factor - 1):

                    case._id = uuid.uuid4().hex
                    case_block = get_case_xml(case, (const.CASE_ACTION_CREATE, const.CASE_ACTION_UPDATE), version='2.0')
                    submit_case_blocks(case_block, domain)
            messages.success(request, "All of %s's cases were exploded by a factor of %d" % (user.raw_username, factor))

    return render(request, template, {
        'domain': domain,
        'users': CommCareUser.by_domain(domain),
    })
