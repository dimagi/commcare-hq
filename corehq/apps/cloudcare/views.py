from casexml.apps.case.models import CommCareCase
from corehq.apps.cloudcare.models import CaseSpec
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.views import logout
from corehq.apps.users.models import CouchUser
from dimagi.utils.web import render_to_response, json_response
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse

def case_list(request):
    pass

cloudcare_api = login_and_domain_required

@login_and_domain_required
def view_case(request, domain, case_id=None):
    context = {}
    case_json = CommCareCase.get(case_id).get_json() if case_id else None
    case_type = case_json['properties']['case_type'] if case_json else None
    case_spec_id = request.GET.get('spec')
    if case_spec_id:
        case_spec = CaseSpec.get(case_spec_id)
    else:
        case_spec = None
        context.update(dict(
            suggested_case_specs=CaseSpec.get_suggested(domain, case_type)
        ))
    context.update({
        'case': case_json,
        'domain': domain,
        'case_spec': case_spec
    })
    return render_to_response(request, 'cloudcare/view_case.html', context)

@cloudcare_api
def get_groups(request, domain, user_id):
    user = CouchUser.get_by_user_id(user_id, domain)
    groups = Group.by_user(user)
    return json_response(sorted([{'label': group.name, 'value': group.get_id} for group in groups], key=lambda x: x['label']))

@cloudcare_api
def get_cases(request, domain):
    user = CouchUser.get_by_user_id(request.GET['user_id'], domain)
    owner_ids = user.get_owner_ids()
    keys = [[owner_id, False] for owner_id in owner_ids]
    cases = CommCareCase.view('case/by_owner', keys=keys, include_docs=True)
    return json_response([case.get_json() for case in cases])
