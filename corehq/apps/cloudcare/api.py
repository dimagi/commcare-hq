from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.models import ApplicationBase, Application



def get_owned_cases(domain, user_id):
    user = CouchUser.get_by_user_id(user_id, domain)
    try:
        owner_ids = user.get_owner_ids()
    except AttributeError:
        owner_ids = [user_id]
    keys = [[owner_id, False] for owner_id in owner_ids]
    cases = CommCareCase.view('case/by_owner', keys=keys, include_docs=True)
    return [case.get_json() for case in cases]

def get_apps(domain):
    return map(lambda app: app._doc, 
               filter(lambda app: app.doc_type == "Application",
                      ApplicationBase.view('app_manager/applications_brief', 
                                           startkey=[domain], endkey=[domain, {}])))

def get_app(domain, app_id):
    app = Application.get(app_id)
    assert(app.domain == domain)
    return app._doc
    