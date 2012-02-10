from casexml.apps.case.models import CommCareCase
from corehq.apps.cloudcare.models import CaseSpec
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.views import logout
from corehq.apps.users.models import CouchUser
from dimagi.utils.web import render_to_response, json_response
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse

def case_list(request):
    pass

def view_case(request, domain, case_id):
    case = CommCareCase.get(case_id)
    case_spec_id = request.GET.get('spec')
    case_spec = CaseSpec.get(case_spec_id)
    return render_to_response(request, 'cloudcare/view_case.html', {
        'case': case.get_json(),
        'domain': domain,
        'case_spec': case_spec
    })

def create_case(request, domain):
    case_spec_id = request.GET.get('spec')
    case_spec = CaseSpec.get(case_spec_id)
    return render_to_response(request, 'cloudcare/view_case.html', {
        'case': None,
        'domain': domain,
        'case_spec': case_spec
    })


def get_groups(request, domain, user_id):
    user = CouchUser.get_by_user_id(user_id, domain)
    groups = Group.by_user(user)
    return json_response(sorted([{'label': group.name, 'value': group.get_id} for group in groups], key=lambda x: x['label']))

def get_cases(request, domain):
    user = CouchUser.get_by_user_id(request.GET['user_id'], domain)
    owner_ids = user.get_owner_ids()
    keys = [[owner_id, False] for owner_id in owner_ids]
    cases = CommCareCase.view('case/by_owner', keys=keys, include_docs=True)
    return json_response([case.get_json() for case in cases])
