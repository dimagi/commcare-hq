import copy
import logging

from couchdbkit.resource import ResourceNotFound
import datetime
import redis
from casexml.apps.case.signals import cases_received, case_post_save
from couchforms.models import XFormInstance
from dimagi.utils.chunked import chunked
from casexml.apps.case.exceptions import (
    IllegalCaseId,
    NoDomainProvided,
    ReconciliationError,
)
from django.conf import settings
from dimagi.utils.couch.database import iter_docs

from casexml.apps.case import const
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml.parser import case_update_from_block
from dimagi.utils.logging import notify_exception


def process_cases(xform, config=None):
    """
    Creates or updates case objects which live outside of the form.

    If reconcile is true it will perform an additional step of
    reconciling the case update history after the case is processed.
    """

    assert getattr(settings, 'UNIT_TESTING', False)
    domain = get_and_check_xform_domain(xform)

    with CaseDbCache(domain=domain, lock=True, deleted_ok=True) as case_db:
        cases = process_cases_with_casedb(xform, case_db, config=config)

    docs = [xform] + cases
    now = datetime.datetime.utcnow()
    for case in cases:
        case.server_modified_on = now
    XFormInstance.get_db().bulk_save(docs)
    for case in cases:
        case_post_save.send(CommCareCase, case=case)
    return cases


def process_cases_with_casedb(xform, case_db, config=None):
    config = config or CaseProcessingConfig()
    cases = get_or_update_cases(xform, case_db).values()

    if config.reconcile:
        for c in cases:
            c.reconcile_actions(rebuild=True)

    # attach domain and export tag if domain is there
    if hasattr(xform, "domain"):
        domain = xform.domain

        def attach_extras(case):
            case.domain = domain
            if domain:
                assert hasattr(case, 'type')
                case['#export_tag'] = ["domain", "type"]
            return case

        cases = [attach_extras(case) for case in cases]

    # handle updating the sync records for apps that use sync mode

    relevant_log = xform.get_sync_token()
    if relevant_log:
        # in reconciliation mode, things can be unexpected
        relevant_log.strict = config.strict_asserts
        from casexml.apps.case.util import update_sync_log_with_checks
        update_sync_log_with_checks(relevant_log, xform, cases, case_db,
                                    case_id_blacklist=config.case_id_blacklist)

        if config.reconcile:
            relevant_log.reconcile_cases()
            relevant_log.save()

    try:
        cases_received.send(sender=None, xform=xform, cases=cases)
    except Exception as e:
        # don't let the exceptions in signals prevent standard case processing
        notify_exception(
            None,
            'something went wrong sending the cases_received signal '
            'for form %s: %s' % (xform._id, e)
        )

    for case in cases:
        if not case.check_action_order():
            try:
                case.reconcile_actions(rebuild=True, xforms={xform._id: xform})
            except ReconciliationError:
                pass
        case_db.mark_changed(case)

    return cases


class CaseProcessingConfig(object):
    def __init__(self, reconcile=False, strict_asserts=True, case_id_blacklist=None):
        self.reconcile = reconcile
        self.strict_asserts = strict_asserts
        self.case_id_blacklist = case_id_blacklist or []

    def __repr__(self):
        return 'reconcile: {reconcile}, strict: {strict}, ids: {ids}'.format(
            reconcile=self.reconcile,
            strict=self.strict_asserts,
            ids=", ".join(self.case_id_blacklist)
        )


class CaseDbCache(object):
    """
    A temp object we use to keep a cache of in-memory cases around
    so we can get the latest updates even if they haven't been saved
    to the database. Also provides some type checking safety.
    """
    def __init__(self, domain=None, strip_history=False, deleted_ok=False,
                 lock=False):
        self.cache = {}
        self.domain = domain
        self.strip_history = strip_history
        self.deleted_ok = deleted_ok
        self.lock = lock
        self.locks = []
        self._changed = set()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for lock in self.locks:
            if lock:
                try:
                    lock.release()
                except redis.ConnectionError:
                    pass

    def validate_doc(self, doc):
        if self.domain and doc.domain != self.domain:
            raise IllegalCaseId("Bad case id")
        elif doc.doc_type == 'CommCareCase-Deleted':
            if not self.deleted_ok:
                raise IllegalCaseId("Case [%s] is deleted " % doc.get_id)
        elif doc.doc_type != 'CommCareCase':
            raise IllegalCaseId(
                "Bad case doc type! "
                "This usually means you are using a bad value for case_id."
            )

    def get(self, case_id):
        if not case_id:
            raise IllegalCaseId('case_id must not be empty')
        if case_id in self.cache:
            return self.cache[case_id]

        try:
            if self.strip_history:
                case_doc = CommCareCase.get_lite(case_id)
            elif self.lock:
                try:
                    case_doc, lock = CommCareCase.get_locked_obj(_id=case_id)
                except redis.ConnectionError:
                    case_doc = CommCareCase.get(case_id)
                else:
                    self.locks.append(lock)
            else:
                case_doc = CommCareCase.get(case_id)
        except ResourceNotFound:
            return None

        self.validate_doc(case_doc)
        self.cache[case_id] = case_doc
        return case_doc
        
    def set(self, case_id, case):
        self.cache[case_id] = case
        
    def doc_exist(self, case_id):
        return case_id in self.cache or CommCareCase.get_db().doc_exist(case_id)

    def in_cache(self, case_id):
        return case_id in self.cache

    def populate(self, case_ids):

        def _iter_raw_cases(case_ids):
            if self.strip_history:
                for ids in chunked(case_ids, 100):
                    for row in CommCareCase.get_db().view("case/get_lite", keys=ids, include_docs=False):
                        yield row['value']
            else:
                for raw_case in iter_docs(CommCareCase.get_db(), case_ids):
                    yield raw_case

        for raw_case in  _iter_raw_cases(case_ids):
            case = CommCareCase.wrap(raw_case)
            self.set(case._id, case)

    def mark_changed(self, case):
        assert self.cache.get(case.case_id) is case
        self._changed.add(case.case_id)

    def get_changed(self):
        return [self.cache[case_id] for case_id in self._changed]

    def clear_changed(self):
        self._changed = set()


def get_and_check_xform_domain(xform):
    try:
        domain = xform.domain
    except AttributeError:
        domain = None

    if not domain and settings.CASEXML_FORCE_DOMAIN_CHECK:
        raise NoDomainProvided()

    return domain


def get_or_update_cases(xform, case_db):
    """
    Given an xform document, update any case blocks found within it,
    returning a dictionary mapping the case ids affected to the
    couch case document objects
    """
    case_updates = get_case_updates(xform)

    for case_update in case_updates:
        case_doc = _get_or_update_model(case_update, xform, case_db)
        if case_doc:
            # todo: legacy behavior, should remove after new case processing
            # is fully enabled.
            if xform._id not in case_doc.xform_ids:
                case_doc.xform_ids.append(xform.get_id)
            case_db.set(case_doc.case_id, case_doc)
        else:
            logging.error(
                "XForm %s had a case block that wasn't able to create a case! "
                "This usually means it had a missing ID" % xform.get_id
            )

    # at this point we know which cases we want to update so sopy this away
    # this prevents indices that end up in the cache from being added to the return value
    touched_cases = copy.copy(case_db.cache)

    # once we've gotten through everything, validate all indices
    def _validate_indices(case):
        if case.indices:
            for index in case.indices:
                # call get and not doc_exists to force domain checking
                # see CaseDbCache.validate_doc
                referenced_case = case_db.get(index.referenced_id)

                if not referenced_case:
                    # just log, don't raise an error or modify the index
                    logging.error(
                        "Case '%s' references non-existent case '%s'",
                        case.get_id,
                        index.referenced_id,
                    )

    [_validate_indices(case) for case in case_db.cache.values()]

    return touched_cases


def _get_or_update_model(case_update, xform, case_db):
    """
    Gets or updates an existing case, based on a block of data in a
    submitted form.  Doesn't save anything.
    """

    case = case_db.get(case_update.id)

    if case is None:
        case = CommCareCase.from_case_update(case_update, xform)
        return case
    else:
        case.update_from_case_update(case_update, xform)
        return case


def is_device_report(doc):
    """exclude device reports"""
    device_report_xmlns = "http://code.javarosa.org/devicereport"
    def _from_form_dict(doc):
        return "@xmlns" in doc and doc["@xmlns"] == device_report_xmlns
    def _from_xform_instance(doc):
        return "xmlns" in doc and doc["xmlns"] == device_report_xmlns

    return _from_form_dict(doc) or _from_xform_instance(doc)


def has_case_id(case_block):
    return const.CASE_TAG_ID in case_block or const.CASE_ATTR_ID in case_block


def extract_case_blocks(doc):
    """
    Extract all case blocks from a document, returning an array of dictionaries
    with the data in each case.

    The json returned is not normalized for casexml version;
    for that get_case_updates is better.

    """

    if isinstance(doc, XFormInstance):
        doc = doc.form
    return list(_extract_case_blocks(doc))


def _extract_case_blocks(data):
    """
    helper for extract_case_blocks

    data must be json representing a node in an xform submission

    """
    if isinstance(data, list):
        for item in data:
            for case_block in _extract_case_blocks(item):
                yield case_block
    elif isinstance(data, dict) and not is_device_report(data):
        for key, value in data.items():
            if const.CASE_TAG == key:
                # it's a case block! Stop recursion and add to this value
                if isinstance(value, list):
                    case_blocks = value
                else:
                    case_blocks = [value]

                for case_block in case_blocks:
                    if has_case_id(case_block):
                        yield case_block
            else:
                for case_block in _extract_case_blocks(value):
                    yield case_block
    else:
        return


def get_case_updates(xform):
    return [case_update_from_block(cb) for cb in extract_case_blocks(xform)]


def get_case_ids_from_form(xform):
    return set(cu.id for cu in get_case_updates(xform))


def cases_referenced_by_xform(xform):
    """
    JSON repr of XFormInstance -> [CommCareCase]
    """
    case_ids = get_case_ids_from_form(xform)

    cases = [CommCareCase.wrap(doc)
             for doc in iter_docs(CommCareCase.get_db(), case_ids)]

    domain = get_and_check_xform_domain(xform)
    if domain:
        for case in cases:
            assert case.domain == domain

    return cases
