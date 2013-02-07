import rawes
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.elastic import get_es
from corehq.pillows import ExchangePillow, CasePillow,XFormPillow
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

def check_exchange_index():
    latest_snapshot = Domain.get_db().view('domain/published_snapshots', limit=1, descending=True, include_docs=True).one()
    if latest_snapshot is not None:
        doc_id = latest_snapshot['id']
        couch_rev = latest_snapshot['doc']['_rev']
        return _check_es_rev(ExchangePillow.es_index, doc_id, couch_rev)
    else:
        return {"%s_status" % ExchangePillow.es_index: False, "%s_message" % ExchangePillow.es_index: "Exchange stale" }

def check_xform_index():
    latest_xforms = _get_latest_xforms()

    for xform in latest_xforms:
        doc_id = xform['id']
        xform_doc = XFormInstance.get_db().get(doc_id)
        couch_rev = xform_doc['_rev']
        return _check_es_rev(XFormPillow.es_alias, doc_id, couch_rev)
    return {"%s_status" % XFormPillow.es_alias: False, "%s_message" % XFormPillow.es_alias: "XForms stale" }



def _get_latest_xforms(limit=100):
    db = XFormInstance.get_db()
    recent_xforms = db.view('hqadmin/forms_over_time', reduce=False, limit=100, descending=True)
    return recent_xforms

def _check_es_rev(index, doc_id, couch_rev):
    es = get_es()
    doc_id_query = {
        "filter": {
            "ids": { "values": [ doc_id ] }
        },
        "fields": [ "_id", "_rev" ]
    }

    try:
        res = es[index].get('_search', data=doc_id_query)
        status=False
        message="Not in sync"

        if res.has_key('hits'):
            if res['hits'].get('total', 0) == 0:
                status=False
                #if doc doesn't exist it's def. not in sync
                message="Not in sync %s" % index
            elif res['hits'].has_key('hits'):
                fields = res['hits']['hits'][0]['fields']
                if fields['_rev'] == couch_rev:
                    status=True
                    message="%s OK" % index
                else:
                    status=False
                    #less likely, but if it's there but the rev is off
                    message="Not in sync - %s stale" % index
        else:
            status=False
            message="Not in sync - query failed"
    except Exception, ex:
        message = "ES Error: %s" % ex
        status=False
    return {"%s_status" % index: status, "%s_message" % index: message }


def check_case_index():
    """
    Verify couch case view and ES views are up to date with the latest xform to update a case, and that the revs are in sync.
    Query recent xforms and their cases, as this is a more accurate way to get case changes in the wild with existing working views
    """
    casedb = CommCareCase.get_db()
    recent_xforms = _get_latest_xforms()
    for xform in recent_xforms:
        xform_id = xform['id']
        #just check to see if any of these recent forms have a case associated with them - they should...
        casedoc = casedb.view('case/by_xform_id', reduce=False, include_docs=True, key=xform_id, limit=1).one()
        if casedoc is not None:
            couch_rev = casedoc['doc']['_rev']
            doc_id = casedoc['doc']['_id']
            return _check_es_rev(CasePillow.es_alias, doc_id, couch_rev)
    #this could be if there's 100 devicelogs that come in
    message = "No recent xforms with case ids - will try again later"

    return {"%s_status" % CasePillow.es_alias: False, "%s_message" % CasePillow.es_alias: message }
