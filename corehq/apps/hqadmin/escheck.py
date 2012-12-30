import rawes
from casexml.apps.case.models import CommCareCase
from corehq.elastic import get_es
from couchforms.models import XFormInstance
from django.conf import settings

CLUSTER_HEALTH = 'cluster_health'
def check_cluster_health():
    """
    The color state of the cluster health is just a simple indicator for how a cluster is running
    It'll mainly be useful for finding out if shards are in good/bad state (red)

    There are better realtime tools for monitoring ES clusters which should probably be looked at. specifically paramedic or bigdesk
    """
    ret = {}
    es = get_es()
    cluster_health = es.get('_cluster/health')
    ret[CLUSTER_HEALTH] = cluster_health['status']
    return ret


def check_case_index():
    """
    Verify couch case view and ES views are up to date with the latest xform to update a case, and that the revs are in sync.
    """
    db = XFormInstance.get_db()
    casedb = CommCareCase.get_db()
    #query case stuff
    recent_xforms = db.view('hqadmin/forms_over_time', reduce=False, limit=100)
    es = get_es()
    #xform_ids = [x['id'] for x in recent_xforms]
    for xform in recent_xforms:
        xform_id = xform['id']
        #just check to see if any of these recent forms have an xform
        casedoc = casedb.view('case/by_xform_id', reduce=False, include_docs=True, key=xform_id, limit=1).one()
        if casedoc is not None:
            #print casedoc.to_json().keys()
            couch_rev = casedoc['doc']['_rev']
            case_id = casedoc['doc']['_id']
            case_id_query = {
                "filter": {
                    "ids": { "values": [ case_id ] }
                },
                "fields": [ "_id", "_rev" ]
            }

            try:
                res = es['hqcases'].get('_search', data=case_id_query)
                print couch_rev
                print case_id
                status=False
                message="Not in sync"

                if res.has_key('hits'):
                    if res['hits'].get('total', 0) == 0:
                        status=False
                        message="Not in sync - case_id"
                    elif res['hits'].has_key('hits'):
                        fields = res['hits']['hits'][0]['fields']
                        if fields['_rev'] == couch_rev:
                            status=True
                            message="In sync"
                        else:
                            status=False
                            message="Not in sync - case outu of date"
                else:
                    status=False
                    message="Not in sync - query failed"
            except Exception, ex:
                message = "ES Error: %s" % ex
                status=False
            return dict(case_status=status, case_message=message)

