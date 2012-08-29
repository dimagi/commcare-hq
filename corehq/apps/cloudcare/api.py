from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.models import ApplicationBase, Application

def get_all_cases(domain, include_closed=False):
    """
    Get all cases in a domain.
    """
    cases = CommCareCase.view('hqcase/types_by_domain', 
                              startkey=[domain],
                              endkey=[domain, {}],
                              reduce=False,
                              include_docs=True)
    if not include_closed:
        cases = filter(lambda case: not case.closed, cases)
    return [case.get_json() for case in cases]


def get_owned_cases(domain, user_id):
    """
    Get all cases in a domain owned by a particular user.
    """
    user = CouchUser.get_by_user_id(user_id, domain)
    try:
        owner_ids = user.get_owner_ids()
    except AttributeError:
        owner_ids = [user_id]
    keys = [[owner_id, False] for owner_id in owner_ids]
    cases = CommCareCase.view('case/by_owner', keys=keys, include_docs=True, reduce=False)
    return [case.get_json() for case in cases]

def get_cloudcare_apps(domain):
    return map(lambda app: app._doc, 
               ApplicationBase.view('cloudcare/cloudcare_apps', 
                                    startkey=[domain], endkey=[domain, {}]))

def get_app(domain, app_id):
    app = Application.get(app_id)
    assert(app.domain == domain)
    return app._doc


