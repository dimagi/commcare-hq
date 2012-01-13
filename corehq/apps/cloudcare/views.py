from casexml.apps.case.models import CommCareCase
from dimagi.utils.web import render_to_response

def case_list(request):
    pass

def view_case(request, domain, case_id):
    case = CommCareCase.get(case_id)
    owner_ids = request.couch_user.get_owner_ids()
    return render_to_response(request, 'cloudcare/view_case.html', {
        'case': {
            'case_id': case.case_id,
            'owner_id': case.owner_id or case.user_id,
        },
        'owner_ids': owner_ids
    })