# stub views file
from collections import defaultdict
from copy import deepcopy
import json
from django.http import HttpResponse
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reports.views import user_id_to_username
from dimagi.utils.web import render_to_response

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
    return render_to_response(request, template, {"domain": domain})