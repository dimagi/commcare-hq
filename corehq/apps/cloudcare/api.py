from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase



def get_owned_cases(domain, user_id):
    user = CouchUser.get_by_user_id(user_id, domain)
    owner_ids = user.get_owner_ids()
    keys = [[owner_id, False] for owner_id in owner_ids]
    cases = CommCareCase.view('case/by_owner', keys=keys, include_docs=True)
    return [case.get_json() for case in cases]
    