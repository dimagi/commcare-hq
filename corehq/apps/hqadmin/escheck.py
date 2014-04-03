import logging
from datetime import datetime
import time

from couchdbkit import ResourceNotFound

from casexml.apps.case.models import CommCareCase
from corehq import Domain
from corehq.elastic import get_es
from corehq.pillows.case import CasePillow
from corehq.pillows.reportcase import ReportCasePillow
from corehq.pillows.reportxform import ReportXFormPillow
from corehq.pillows.xform import XFormPillow
from couchforms.models import XFormInstance
from django.conf import settings


CLUSTER_HEALTH = 'cluster_health'
def check_es_cluster_health():
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


def check_index_by_doc(es_index, db, doc_id, interval=10):
    """
    Given a doc, update it in couch (meaningless save that updates rev)
    and check to make sure that ES will eventually see it after some arbitrary delay
    """
    target_rev = None
    try:
        couch_doc = db.open_doc(doc_id if doc_id else "")
        save_results = db.save_doc(couch_doc)
        target_rev = save_results['rev']
    except ResourceNotFound:
        pass

    time.sleep(interval)
    return _check_es_rev(es_index, doc_id, target_rev)


def is_real_submission(xform_view_row):
    """
    helper filter function for filtering hqadmin/forms_over_time
    just filters out devicereports
    """
    return xform_view_row['doc']['xmlns'] != 'http://code.javarosa.org/devicereport'



def check_reportxform_es_index(doc_id=None, interval=10):
    do_check = False
    for domain in settings.ES_XFORM_FULL_INDEX_DOMAINS:
        domain_doc = Domain.get_by_name(domain)
        if domain_doc is not None:
            do_check = True
            break

    if do_check:
        db = XFormInstance.get_db()
        es_index = ReportXFormPillow.es_alias

        check_doc_id = doc_id if doc_id else  _get_latest_doc_from_index(es_index, 'received_on')
        return check_index_by_doc(es_index, db, check_doc_id, interval=interval)
    else:
        return {}


def check_xform_es_index(doc_id=None, interval=10):
    db = XFormInstance.get_db()
    es_index = XFormPillow.es_alias

    check_doc_id = doc_id if doc_id else _get_latest_doc_id(db, 'XFormInstance', skipfunc=is_real_submission)
    return check_index_by_doc(es_index, db, check_doc_id, interval=interval)


def is_case_recent(case_view_row):
    """
    helper filter function for filtering hqadmin/cases_over_time
    the view emits a key [YYYY, MM] this just sanity checks to make sure that it's a recent case,
    not some wrongly future emitted case
    """
    if case_view_row['key'] > [datetime.utcnow().year, datetime.utcnow().month]:
        return False
    else:
        return True

def check_reportcase_es_index(doc_id=None, interval=10):
    do_check = False
    for domain in settings.ES_CASE_FULL_INDEX_DOMAINS:
        domain_doc = Domain.get_by_name(domain)
        if domain_doc is not None:
            do_check = True
            break

    if do_check:
        db = CommCareCase.get_db()
        es_index = ReportCasePillow.es_alias

        check_doc_id = doc_id if doc_id else _get_latest_doc_from_index(es_index, sort_field='opened_on')
        return check_index_by_doc(es_index, db, check_doc_id, interval=interval)
    else:
        return {}


def check_case_es_index(doc_id=None, interval=10):
    db = CommCareCase.get_db()
    es_index = CasePillow.es_alias

    check_doc_id = doc_id if doc_id else _get_latest_doc_id(db, 'CommCareCase', skipfunc=is_case_recent)
    return check_index_by_doc(es_index, db, check_doc_id, interval=interval)


def _get_latest_doc_from_index(es_index, sort_field):
    """
    Query elasticsearch index sort descending by the sort field
    and get the doc_id back so we can then do a rev-update check.

    This si because there's no direct view known ahead of time what's inside the report* index,
    so just get it directly from the index and do the modify check workflow.
    """
    recent_query = {
        "filter": {
            "match_all": {}
        },
        "sort": {sort_field: "desc"},
        "size": 1
    }
    es = get_es()

    try:
        res = es[es_index].get('_search', data=recent_query)
        if 'hits' in res:
            if 'hits' in res['hits']:
                result = res['hits']['hits'][0]
                return result['_source']['_id']

    except Exception, ex:
        logging.error("Error querying get_latest_doc_from_index[%s]: %s" % (es_index, ex))
        return None



def _get_latest_doc_id(db, doc_type, skip=0, limit=100, skipfunc=None):
    """
    Get the most recent doc_id from the relevant views emitting over time.

    'CommCareCase' | 'XFormInstance'
    hqadmin/cases_over_time or hqadmin/forms_over_time

    skipfunc = filter function for getting stuff out that we don't care about.

    for xforms, this is for filtering out devicelogs
    for cases, filtering out dates in the future
    """
    doc_type_views = {
        'CommCareCase': 'hqadmin/cases_over_time',
        'XFormInstance': 'hqadmin/forms_over_time'
    }

    if doc_type in doc_type_views:
        view_name = doc_type_views[doc_type]
    else:
        raise Exception("Don't know what to do with that doc_type to check an index: %s" % doc_type)
    def _call_view(skip, limit):
        return db.view(view_name, reduce=False, limit=limit, skip=skip, include_docs=True, descending=True)
    filtered_docs = []

    while True:
        raw_docs = _call_view(skip, limit)
        filtered_docs = filter(skipfunc, raw_docs)
        if len(filtered_docs) > 0:
            break
        skip += limit
        if skip == 5000:
            #sanity check if we get a deluge of bad data, just return anything we got
            break

    if len(filtered_docs) > 0:
        return filtered_docs[0]['id']
    else:
        return None


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
    return {index: {"index": index, "status": status, "message": message}}


