import logging
import time

from django.conf import settings

from couchdbkit import ResourceNotFound

from casexml.apps.case.models import CommCareCase
from corehq.util.es.interface import ElasticsearchInterface
from couchforms.models import XFormInstance
from dimagi.utils.logging import notify_error

from corehq.apps.domain.models import Domain
from corehq.apps.hqadmin.history import get_recent_changes
from corehq.elastic import get_es_new
from corehq.pillows.mappings.case_mapping import CASE_ES_ALIAS
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_ES_ALIAS
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_ALIAS
from corehq.pillows.mappings.xform_mapping import XFORM_ALIAS


def check_es_cluster_health():
    """
    The color state of the cluster health is just a simple indicator for how a cluster is running
    It'll mainly be useful for finding out if shards are in good/bad state (red)

    There are better realtime tools for monitoring ES clusters which should probably be looked at. specifically paramedic or bigdesk
    """
    ret = {}
    es = get_es_new()  # assign to variable to avoid weak reference error
    cluster_health = es.cluster.health()
    return cluster_health['status']


def check_index_by_doc(es_alias, db, doc_id, interval=10):
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
    return _check_es_rev(es_alias, doc_id, target_revs)


def check_reportxform_es_index(doc_id=None, interval=10):
    do_check = False
    for domain in settings.ES_XFORM_FULL_INDEX_DOMAINS:
        domain_doc = Domain.get_by_name(domain)
        if domain_doc is not None:
            do_check = True
            break

    if do_check:
        db = XFormInstance.get_db()
        es_alias = REPORT_XFORM_ALIAS

        check_doc_id = doc_id if doc_id else _get_latest_doc_from_index(es_alias, 'received_on')
        return check_index_by_doc(es_alias, db, check_doc_id, interval=interval)
    else:
        return {}


def check_xform_es_index(interval=10):
    try:
        doc_id, doc_rev = get_last_change_for_doc_class(XFormInstance)
    except StopIteration:
        return None
    time.sleep(interval)
    return _check_es_rev(XFORM_ALIAS, doc_id, [doc_rev])


def check_reportcase_es_index(doc_id=None, interval=10):
    do_check = False
    for domain in settings.ES_CASE_FULL_INDEX_DOMAINS:
        domain_doc = Domain.get_by_name(domain)
        if domain_doc is not None:
            do_check = True
            break

    if do_check:
        db = CommCareCase.get_db()
        es_alias = REPORT_CASE_ES_ALIAS
        check_doc_id = doc_id if doc_id else _get_latest_doc_from_index(es_alias, sort_field='opened_on')
        return check_index_by_doc(es_alias, db, check_doc_id, interval=interval)
    else:
        return {}


def check_case_es_index(interval=10):
    try:
        doc_id, doc_rev = get_last_change_for_doc_class(CommCareCase)
    except StopIteration:
        return None
    time.sleep(interval)
    return _check_es_rev(CASE_ES_ALIAS, doc_id, [doc_rev])


def get_last_change_for_doc_class(doc_class):
    """
    return _id and _rev of the last doc of `doc_type` in changes feed

    raise StopIteration if not found in last 100 changes
    """
    db = doc_class.get_db()
    doc_type = doc_class._doc_type
    return next(
        (change['id'], change['rev']) for change in get_recent_changes(db, 100)
        if change['doc_type'] == doc_type
    )


def _get_latest_doc_from_index(es_alias, sort_field):
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
    es_interface = ElasticsearchInterface(get_es_new())

    try:
        res = es_interface.search(es_alias, body=recent_query)
        if 'hits' in res:
            if 'hits' in res['hits']:
                result = res['hits']['hits'][0]
                return result['_source']['_id']

    except Exception as ex:
        logging.error("Error querying get_latest_doc_from_index[%s]: %s" % (es_alias, ex))
        return None


def _check_es_rev(es_alias, doc_id, couch_revs):
    """
    Specific docid and rev checker.

    es_alias: Elasticsearch alias
    doc_id: id to query in ES
    couch_rev: target couch_rev that you want to match
    """
    es_interface = ElasticsearchInterface(get_es_new())
    doc_id_query = {
        "filter": {
            "ids": {"values": [doc_id]}
        },
        "fields": ["_id", "_rev"]
    }

    try:
        res = es_interface.search(es_alias, body=doc_id_query)
        status = False
        message = "Not in sync"

        if 'hits' in res:
            if res['hits'].get('total', 0) == 0:
                status = False
                # if doc doesn't exist it's def. not in sync
                message = "Not in sync %s" % es_alias
            elif 'hits' in res['hits']:
                fields = res['hits']['hits'][0]['fields']
                if fields['_rev'] in couch_revs:
                    status = True
                    message = "%s OK" % es_alias
                else:
                    status = False
                    # less likely, but if it's there but the rev is off
                    message = "Not in sync - %s stale" % es_alias
        else:
            status = False
            message = "Not in sync - query failed"
            notify_error("%s: %s" % (message, str(res)))
    except Exception as ex:
        message = "ES Error: %s" % ex
        status = False
    return {es_alias: {"es_alias": es_alias, "status": status, "message": message}}
