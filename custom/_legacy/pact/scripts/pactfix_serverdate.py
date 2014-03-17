import simplejson
from casexml.apps.case.models import CommCareCase
from pact.enums import PACT_HP_GROUP_ID


def run():
    print "starting out"
    pact_cases = CommCareCase.view('case/by_owner_lite', key=[PACT_HP_GROUP_ID, True],
                                   include_docs=True, reduce=False).all()

    for c in pact_cases:
        print "#### Case %s" % c._id
        for action in c.actions:
            if getattr(action, 'server_date', None) is None:
                print "\taction is none!"
                print "\t%s" % simplejson.dumps(action.to_json(), indent=4)
