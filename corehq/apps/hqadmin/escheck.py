import logging
from datetime import datetime
import time

from couchdbkit import ResourceNotFound
import itertools

from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.apps.hqadmin.dbaccessors import iter_all_forms_most_recent_first, \
    iter_all_cases_most_recent_first
from corehq.elastic import get_es_new
from corehq.pillows.mappings.case_mapping import CASE_INDEX
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_INDEX
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from couchforms.models import XFormInstance
from django.conf import settings
from dimagi.utils.logging import notify_error


CLUSTER_HEALTH = 'cluster_health'
def check_es_cluster_health():
    """
    The color state of the cluster health is just a simple indicator for how a cluster is running
    It'll mainly be useful for finding out if shards are in good/bad state (red)

    There are better realtime tools for monitoring ES clusters which should probably be looked at. specifically paramedic or bigdesk
    """
    ret = {}
    cluster_health = get_es_new().cluster.health()
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
        # due to a way that long polling works we have to save it twice because the pillow
        # doesn't seem to pick up on the last line until there is a new one available.
        target_revs = []
        for i in range(2):
            save_results = db.save_doc(couch_doc)
            target_revs.append(save_results['rev'])

    except ResourceNotFound:
        pass

    time.sleep(interval)
    return _check_es_rev(es_index, doc_id, target_revs)


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
        es_index = REPORT_XFORM_INDEX

        check_doc_id = doc_id if doc_id else _get_latest_doc_from_index(es_index, 'received_on')
        return check_index_by_doc(es_index, db, check_doc_id, interval=interval)
    else:
        return {}


def check_xform_es_index(interval=10):
    db = XFormInstance.get_db()
    forms = iter_all_forms_most_recent_first()
    check_doc_id = _get_first_id_or_none(forms, skipfunc=is_real_submission)
    return check_index_by_doc(XFORM_INDEX, db, check_doc_id, interval=interval)


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
        es_index = REPORT_CASE_INDEX
        check_doc_id = doc_id if doc_id else _get_latest_doc_from_index(es_index, sort_field='opened_on')
        return check_index_by_doc(es_index, db, check_doc_id, interval=interval)
    else:
        return {}


def check_case_es_index(interval=10):
    db = CommCareCase.get_db()
    cases = iter_all_cases_most_recent_first()
    check_doc_id = _get_first_id_or_none(cases, skipfunc=is_case_recent)
    return check_index_by_doc(CASE_INDEX, db, check_doc_id, interval=interval)


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
    es = get_es_new()

    try:
        res = es.search(es_index, body=recent_query)
        if 'hits' in res:
            if 'hits' in res['hits']:
                result = res['hits']['hits'][0]
                return result['_source']['_id']

    except Exception, ex:
        logging.error("Error querying get_latest_doc_from_index[%s]: %s" % (es_index, ex))
        return None


def _get_first_id_or_none(docs, skipfunc=None):

    # don't check more than 5000 docs, not worth it
    for doc in itertools.islice(docs, 0, 5000):
        if skipfunc(doc):
            return doc['id']

    return None


def _check_es_rev(index, doc_id, couch_revs):
    """
    Specific docid and rev checker.

    index: Elasticsearch index
    doc_id: id to query in ES
    couch_rev: target couch_rev that you want to match
    """
    es = get_es_new()
    doc_id_query = {
        "filter": {
            "ids": {"values": [doc_id]}
        },
        "fields": ["_id", "_rev"]
    }

    try:
        res = es.search(index, body=doc_id_query)
        status = False
        message = "Not in sync"

        if res.has_key('hits'):
            if res['hits'].get('total', 0) == 0:
                status = False
                # if doc doesn't exist it's def. not in sync
                message = "Not in sync %s" % index
            elif 'hits' in res['hits']:
                fields = res['hits']['hits'][0]['fields']
                if fields['_rev'] in couch_revs:
                    status = True
                    message = "%s OK" % index
                else:
                    status = False
                    # less likely, but if it's there but the rev is off
                    message = "Not in sync - %s stale" % index
        else:
            status = False
            message = "Not in sync - query failed"
            notify_error("%s: %s" % (message, str(res)))
    except Exception, ex:
        message = "ES Error: %s" % ex
        status = False
    return {index: {"index": index, "status": status, "message": message}}
