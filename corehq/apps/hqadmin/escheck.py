from couchdbkit import ResourceNotFound
import rawes
from casexml.apps.case.models import CommCareCase
from corehq.elastic import get_es
from corehq.pillows.case import CasePillow
from corehq.pillows.xform import XFormPillow
from couchforms.models import XFormInstance
from django.conf import settings
import time

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


def check_index_by_doc(es_index, db, doc_id):
    """
    Given a doc, update it in couch (meaningless save that updates rev)
    and check to make sure that ES will eventually see it after some arbitrary delay
    """
    try:
        couch_doc = db.open_doc(doc_id)
        save_results = db.save_doc(couch_doc)
        target_rev = save_results['rev']
        time.sleep(3) #could be less, but just in case
        return _check_es_rev(es_index, doc_id, target_rev)
    except ResourceNotFound:
        pass


def check_xform_index_by_doc(doc_id):
    db = XFormInstance.get_db()
    es_index = XFormPillow.es_alias
    return check_index_by_doc(es_index, db, doc_id)


def check_case_index_by_doc(doc_id):
    db = CommCareCase.get_db()
    es_index = CasePillow.es_alias
    return check_index_by_doc(es_index, db, doc_id)


def check_xform_index_by_view():
    """
    View based xform index checker - to be deprecated
    """
    latest_xforms = _get_latest_xforms()
    found_xform = False
    start_skip = 0
    limit = 100

    while found_xform is False:
        for xform in latest_xforms:
            doc_id = xform['id']
            xform_doc = xform['doc']
            couch_rev = xform_doc['_rev']
            return _check_es_rev(XFormPillow.es_alias, doc_id, couch_rev)
    return {"%s_status" % XFormPillow.es_alias: False, "%s_message" % XFormPillow.es_alias: "XForms stale" }


def _get_latest_xforms(skip=0, limit=100):
    db = XFormInstance.get_db()

    def _do_get_raw_xforms(skip, limit):
        return db.view('hqadmin/forms_over_time', reduce=False, limit=limit, skip=skip, include_docs=True, descending=True)
    raw_xforms = _do_get_raw_xforms(skip, limit)
    recent_xforms = []

    while True:
        recent_xforms = filter(lambda x: x['doc']['xmlns'] != 'http://code.javarosa.org/devicereport', raw_xforms)
        if len(recent_xforms) > 0:
            break
        #all the recent submissions are device logs, keep digging
        skip += limit
        raw_xforms = _do_get_raw_xforms(skip, limit)
        if skip == 5000:
            #sanity check if we get a deluge of devicereports
            return recent_xforms

    return recent_xforms


def _check_es_rev(index, doc_id, couch_rev):
    """
    Specific docid and rev checker.

    index: rawes index
    doc_id: id to query in ES
    couch_rev: target couch_rev that you want to match
    """
    es = get_es()
    doc_id_query = {
        "filter": {
            "ids": {"values": [doc_id]}
        },
        "fields": ["_id", "_rev"]
    }

    try:
        res = es[index].get('_search', data=doc_id_query)
        status = False
        message = "Not in sync"

        if res.has_key('hits'):
            if res['hits'].get('total', 0) == 0:
                status = False
                #if doc doesn't exist it's def. not in sync
                message = "Not in sync %s" % index
            elif 'hits' in res['hits']:
                fields = res['hits']['hits'][0]['fields']
                if fields['_rev'] == couch_rev:
                    status = True
                    message = "%s OK" % index
                else:
                    status = False
                    #less likely, but if it's there but the rev is off
                    message = "Not in sync - %s stale" % index
        else:
            status = False
            message = "Not in sync - query failed"
    except Exception, ex:
        message = "ES Error: %s" % ex
        status = False
    return {"%s_status" % index: status, "%s_message" % index: message}


def check_case_index_by_view():
    """
    View based case index checker - to be deprecated
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
