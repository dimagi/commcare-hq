import json
import itertools
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.models import ApplicationBase, Application
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.decorators import inline

# todo: Make these api functions use generators for streaming
# so that a limit call won't fetch more docs than it needs to
# This could be achieved with something like CommCareCase.paging_view that
# returns a generator but internally batches couch requests
# potentially doubling the batch-size each time in case it really is a lot of data

def get_all_cases(domain, include_closed=False, case_type=None):
    """
    Get all cases in a domain.
    """
    key = [domain, case_type or {}, {}]
    view_name = 'hqcase/all_cases' if include_closed else 'hqcase/open_cases'
    cases = CommCareCase.view(view_name,
        startkey=key,
        endkey=key + [{}],
        include_docs=True,
        reduce=False,
    ).all()

    return [case.get_json() for case in cases]


def get_owned_cases(domain, user_id, closed=False):
    """
    Get all cases in a domain owned by a particular user.
    """

    try:
        user = CouchUser.get_by_user_id(user_id, domain)
    except KeyError:
        user = None
    try:
        owner_ids = user.get_owner_ids()
    except AttributeError:
        owner_ids = [user_id]

    @list
    @inline
    def keys():
        for owner_id in owner_ids:
            if closed is None:
                yield [owner_id, True]
                yield [owner_id, False]
            else:
                yield [owner_id, closed]

    cases = CommCareCase.view('case/by_owner', keys=keys, include_docs=True, reduce=False)
    # demo_user cases!
    return [case.get_json() for case in cases if case.domain == domain]


def get_filtered_cases(domain, user_id=None, filters=None):

    @inline
    def cases():
        """pre-filter cases based on user_id and (if possible) closed"""
        closed = json.loads(filters.get('closed') or 'null')
        case_type = filters.get('properties/case_type')

        if user_id:
            return get_owned_cases(domain, user_id, closed=closed)
        else:
            return get_all_cases(domain, include_closed=closed in (True, None), case_type=case_type)

    if filters:
        def _filter(case):
            for path, val in filters.items():
                if val is None:
                    continue

                actual_val = safe_index(case, path.split("/"))

                if actual_val != val:
                    # closed=false => case.closed == False
                    if val in ('null', 'true', 'false'):
                        if actual_val != json.loads(val):
                            return False
                    else:
                        return False

            return True
        cases = filter(_filter, cases)
    return cases

def get_filters_from_request(request):
    filters = dict(request.REQUEST.items())
    filters.update({
        'user_id': None,
        'closed': ({
            'any': None,
            'true': 'true',
            'false': 'false',
        }.get(filters.get('closed'), 'false')),
        'format': None
    })
    return filters

def get_cloudcare_apps(domain):
    return map(lambda app: app._doc, 
               ApplicationBase.view('cloudcare/cloudcare_apps', 
                                    startkey=[domain], endkey=[domain, {}]))

def get_app(domain, app_id):
    app = Application.get(app_id)
    assert(app.domain == domain)
    return app._doc


