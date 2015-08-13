from __future__ import absolute_import
from collections import defaultdict
import uuid

from xml.etree import ElementTree
import datetime

from django.conf import settings

from casexml.apps.case import const
from casexml.apps.case.const import CASE_ACTION_UPDATE, CASE_ACTION_CREATE
from casexml.apps.case.dbaccessors import get_indexed_case_ids
from casexml.apps.phone.models import SyncLogAssertionError, get_properly_wrapped_sync_log
from casexml.apps.phone.xml import get_case_element
from casexml.apps.stock.models import StockReport
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs


def make_form_from_case_blocks(case_blocks):
    form = ElementTree.Element("data")
    form.attrib['xmlns'] = "https://www.commcarehq.org/test/casexml-wrapper"
    form.attrib['xmlns:jrm'] = "http://openrosa.org/jr/xforms"
    for block in case_blocks:
        form.append(block)
    return ElementTree.tostring(form)


def post_case_blocks(case_blocks, form_extras=None, domain=None):
    """
    Post case blocks.

    Extras is used to add runtime attributes to the form before
    sending it off to the case (current use case is sync-token pairing)
    """
    import couchforms
    from corehq.apps.receiverwrapper.util import DefaultAuthContext

    if form_extras is None:
        form_extras = {}

    domain = domain or form_extras.pop('domain', None)
    if getattr(settings, 'UNIT_TESTING', False):
        from casexml.apps.case.tests.util import TEST_DOMAIN_NAME
        domain = domain or TEST_DOMAIN_NAME

    form = make_form_from_case_blocks(case_blocks)

    form_extras['auth_context'] = (
        form_extras.get('auth_context') or DefaultAuthContext())
    sp = couchforms.SubmissionPost(
        instance=form,
        domain=domain,
        **form_extras
    )
    response, xform, cases = sp.run()
    return xform, cases


def create_real_cases_from_dummy_cases(cases):
    """
    Takes as input a list of unsaved CommCareCase objects

    that don't have any case actions, etc.
    and creates them through the official channel of submitting forms, etc.

    returns a tuple of two lists: forms posted and cases created

    """
    posted_cases = []
    posted_forms = []
    case_blocks_by_domain = defaultdict(list)
    for case in cases:
        if not case.modified_on:
            case.modified_on = datetime.datetime.utcnow()
        if not case._id:
            case._id = uuid.uuid4().hex
        case_blocks_by_domain[case.domain].append(get_case_element(
            case, (CASE_ACTION_CREATE, CASE_ACTION_UPDATE), version='2.0'))
    for domain, case_blocks in case_blocks_by_domain.items():
        form, cases = post_case_blocks(case_blocks, domain=domain)
        posted_forms.append(form)
        posted_cases.extend(cases)
    return posted_forms, posted_cases


def reprocess_form_cases(form, config=None, case_db=None):
    """
    For a given form, reprocess all case elements inside it. This operation
    should be a no-op if the form was sucessfully processed, but should
    correctly inject the update into the case history if the form was NOT
    successfully processed.
    """
    from casexml.apps.case.xform import process_cases, process_cases_with_casedb

    if case_db:
        process_cases_with_casedb([form], case_db, config=config)
    else:
        process_cases(form, config)
    # mark cleaned up now that we've reprocessed it
    if form.doc_type != 'XFormInstance':
        form = XFormInstance.get(form._id)
        form.doc_type = 'XFormInstance'
        form.save()


def get_case_xform_ids(case_id):
    results = XFormInstance.get_db().view('case/form_case_index',
                                          reduce=False,
                                          startkey=[case_id],
                                          endkey=[case_id, {}])

    # also have to add commtrack forms, which may not appear in the form --> case index
    commtrack_reports = StockReport.objects.filter(stocktransaction__case_id=case_id)
    commtrack_forms = commtrack_reports.values_list('form_id', flat=True).distinct()
    return list(set([row['key'][1] for row in results] + list(commtrack_forms)))


def update_sync_log_with_checks(sync_log, xform, cases, case_db,
                                case_id_blacklist=None):
    assert case_db is not None
    from casexml.apps.case.xform import CaseProcessingConfig

    case_id_blacklist = case_id_blacklist or []
    try:
        sync_log.update_phone_lists(xform, cases)
    except SyncLogAssertionError, e:
        if e.case_id and e.case_id not in case_id_blacklist:
            form_ids = get_case_xform_ids(e.case_id)
            case_id_blacklist.append(e.case_id)
            for form_id in form_ids:
                if form_id != xform._id:
                    form = XFormInstance.get(form_id)
                    if form.doc_type == 'XFormInstance':
                        reprocess_form_cases(
                            form,
                            CaseProcessingConfig(
                                strict_asserts=True,
                                case_id_blacklist=case_id_blacklist
                            ),
                            case_db=case_db
                        )
            updated_log = get_properly_wrapped_sync_log(sync_log._id)

            update_sync_log_with_checks(updated_log, xform, cases, case_db,
                                        case_id_blacklist=case_id_blacklist)


def get_indexed_cases(domain, case_ids):
    """
    Given a base list of cases, gets all wrapped cases that they reference
    (parent cases).
    """
    from casexml.apps.case.models import CommCareCase
    return [CommCareCase.wrap(doc) for doc in iter_docs(CommCareCase.get_db(),
                                                        get_indexed_case_ids(domain, case_ids))]


def primary_actions(case):
    return filter(lambda a: a.action_type != const.CASE_ACTION_REBUILD,
                  case.actions)


def iter_cases(case_ids, strip_history=False, wrap=True):
    from casexml.apps.case.models import CommCareCase
    if not strip_history:
        for doc in iter_docs(CommCareCase.get_db(), case_ids):
            yield CommCareCase.wrap(doc) if wrap else doc
    else:
        for case in CommCareCase.bulk_get_lite(case_ids, wrap=wrap):
            yield case
