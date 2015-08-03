from collections import namedtuple
import copy
import logging
import warnings

from couchdbkit import ResourceNotFound
import datetime
from django.db.models import Q
import redis
from casexml.apps.case.dbaccessors import get_reverse_indexed_cases
from casexml.apps.case.signals import cases_received, case_post_save
from casexml.apps.phone.cleanliness import should_track_cleanliness, should_create_flags_on_submission
from casexml.apps.phone.models import OwnershipCleanlinessFlag
from corehq.toggles import LOOSE_SYNC_TOKEN_VALIDATION
from casexml.apps.case.util import iter_cases
from couchforms.models import XFormInstance
from casexml.apps.case.exceptions import (
    IllegalCaseId,
    NoDomainProvided,
    ReconciliationError,
)
from django.conf import settings
from couchforms.util import is_deprecation
from dimagi.utils.couch.database import iter_docs

from casexml.apps.case import const
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml.parser import case_update_from_block
from dimagi.utils.logging import notify_exception


# Lightweight class used to store the dirtyness of a case/owner pair.
DirtinessFlag = namedtuple('DirtinessFlag', ['case_id', 'owner_id'])


class CaseProcessingResult(object):
    """
    Lightweight class used to collect results of case processing
    """
    def __init__(self, domain, cases, dirtiness_flags, track_cleanliness):
        self.domain = domain
        self.cases = cases
        self.dirtiness_flags = dirtiness_flags
        self.track_cleanliness = track_cleanliness

    def get_clean_owner_ids(self):
        dirty_flags = self.get_flags_to_save()
        return {c.owner_id for c in self.cases if c.owner_id and c.owner_id not in dirty_flags}

    def set_cases(self, cases):
        self.cases = cases

    def get_flags_to_save(self):
        return {f.owner_id: f.case_id for f in self.dirtiness_flags}

    def commit_dirtiness_flags(self):
        """
        Updates any dirtiness flags in the database.
        """
        if self.track_cleanliness and self.domain:
            flags_to_save = self.get_flags_to_save()
            if should_create_flags_on_submission(self.domain):
                assert settings.UNIT_TESTING  # this is currently only true when unit testing
                all_touched_ids = set(flags_to_save.keys()) | self.get_clean_owner_ids()
                to_update = {f.owner_id: f for f in OwnershipCleanlinessFlag.objects.filter(
                    domain=self.domain,
                    owner_id__in=list(all_touched_ids),
                )}
                for owner_id in all_touched_ids:
                    if owner_id not in to_update:
                        # making from scratch - default to clean, but set to dirty if needed
                        flag = OwnershipCleanlinessFlag(domain=self.domain, owner_id=owner_id, is_clean=True)
                        if owner_id in flags_to_save:
                            flag.is_clean = False
                            flag.hint = flags_to_save[owner_id]
                        flag.save()
                    else:
                        # updating - only save if we are marking dirty or setting a hint
                        flag = to_update[owner_id]
                        if owner_id in flags_to_save and (flag.is_clean or not flag.hint):
                            flag.is_clean = False
                            flag.hint = flags_to_save[owner_id]
                            flag.save()
            else:
                # only update the flags that are already in the database
                flags_to_update = OwnershipCleanlinessFlag.objects.filter(
                    Q(domain=self.domain),
                    Q(owner_id__in=flags_to_save.keys()),
                    Q(is_clean=True) | Q(hint__isnull=True)
                )
                for flag in flags_to_update:
                    flag.is_clean = False
                    flag.hint = flags_to_save[flag.owner_id]
                    flag.save()


def process_cases(xform, config=None):
    """
    Creates or updates case objects which live outside of the form.

    If reconcile is true it will perform an additional step of
    reconciling the case update history after the case is processed.
    """
    warnings.warn(
        'This function is deprecated. You should be using SubmissionPost.',
        DeprecationWarning,
    )

    assert getattr(settings, 'UNIT_TESTING', False)
    domain = get_and_check_xform_domain(xform)

    with CaseDbCache(domain=domain, lock=True, deleted_ok=True) as case_db:
        case_result = process_cases_with_casedb([xform], case_db, config=config)

    cases = case_result.cases
    docs = [xform] + cases
    now = datetime.datetime.utcnow()
    for case in cases:
        case.server_modified_on = now
    XFormInstance.get_db().bulk_save(docs)

    for case in cases:
        case_post_save.send(CommCareCase, case=case)

    case_result.commit_dirtiness_flags()
    return cases


def process_cases_with_casedb(xforms, case_db, config=None):
    config = config or CaseProcessingConfig()
    case_processing_result = _get_or_update_cases(xforms, case_db)
    cases = case_processing_result.cases
    xform = xforms[0]

    # attach domain and export tag
    domain = xform.domain

    def attach_extras(case):
        case.domain = domain
        if domain:
            assert hasattr(case, 'type')
            case['#export_tag'] = ["domain", "type"]
        return case

    cases = [attach_extras(case) for case in cases]

    # handle updating the sync records for apps that use sync mode
    try:
        relevant_log = xform.get_sync_token()
    except ResourceNotFound:
        if LOOSE_SYNC_TOKEN_VALIDATION.enabled(xform.domain):
            relevant_log = None
        else:
            raise

    if relevant_log:
        # in reconciliation mode, things can be unexpected
        relevant_log.strict = config.strict_asserts
        from casexml.apps.case.util import update_sync_log_with_checks
        update_sync_log_with_checks(relevant_log, xform, cases, case_db,
                                    case_id_blacklist=config.case_id_blacklist)

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

        action_xforms = {action.xform_id for action in case.actions if action.xform_id}
        mismatched_forms = action_xforms ^ set(case.xform_ids)
        if mismatched_forms:
            logging.warning(
                "CASE XFORM MISMATCH /a/{},{}".format(
                    domain,
                    case.case_id
                )
            )

    case_processing_result.set_cases(cases)
    return case_processing_result


class CaseProcessingConfig(object):
    def __init__(self, strict_asserts=True, case_id_blacklist=None):
        self.strict_asserts = strict_asserts
        self.case_id_blacklist = case_id_blacklist if case_id_blacklist is not None else []

    def __repr__(self):
        return 'strict: {strict}, ids: {ids}'.format(
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
                 lock=False, wrap=True, initial=None, xforms=None):
        if initial:
            self.cache = {case['_id']: case for case in initial}
        else:
            self.cache = {}

        self.domain = domain
        self.xforms = xforms if xforms is not None else []
        self.strip_history = strip_history
        self.deleted_ok = deleted_ok
        self.lock = lock
        self.wrap = wrap
        if self.lock and not self.wrap:
            raise ValueError('Currently locking only supports explicitly wrapping cases!')
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
        if self.domain and doc['domain'] != self.domain:
            raise IllegalCaseId("Bad case id")
        elif doc['doc_type'] == 'CommCareCase-Deleted':
            if not self.deleted_ok:
                raise IllegalCaseId("Case [%s] is deleted " % doc['_id'])
        elif doc['doc_type'] != 'CommCareCase':
            raise IllegalCaseId(
                'Bad case doc type! '
                'This usually means you are using a bad value for case_id.'
                'The offending ID is {}'.format(doc['_id'])
            )

    def get(self, case_id):
        if not case_id:
            raise IllegalCaseId('case_id must not be empty')
        if case_id in self.cache:
            return self.cache[case_id]

        try:
            if self.strip_history:
                case_doc = CommCareCase.get_lite(case_id, wrap=self.wrap)
            elif self.lock:
                try:
                    case_doc, lock = CommCareCase.get_locked_obj(_id=case_id)
                except redis.ConnectionError:
                    case_doc = CommCareCase.get(case_id)
                else:
                    self.locks.append(lock)
            else:
                if self.wrap:
                    case_doc = CommCareCase.get(case_id)
                else:
                    case_doc = CommCareCase.get_db().get(case_id)
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
        """
        Populates a set of IDs in the cache in bulk.
        Use this if you know you are going to need to access these later for performance gains.
        Does NOT overwrite what is already in the cache if there is already something there.
        """
        case_ids = set(case_ids) - set(self.cache.keys())
        for case in iter_cases(case_ids, self.strip_history, self.wrap):
            self.set(case['_id'], case)

    def mark_changed(self, case):
        assert self.cache.get(case.case_id) is case
        self._changed.add(case['_id'])

    def get_changed(self):
        return [self.cache[case_id] for case_id in self._changed]

    def clear_changed(self):
        self._changed = set()

    def get_cached_forms(self):
        """
        Get any in-memory forms being processed.
        """
        return {xform._id: xform for xform in self.xforms}


def get_and_check_xform_domain(xform):
    try:
        domain = xform.domain
    except AttributeError:
        domain = None

    if not domain and settings.CASEXML_FORCE_DOMAIN_CHECK:
        raise NoDomainProvided()

    return domain


def _get_or_update_cases(xforms, case_db):
    """
    Given an xform document, update any case blocks found within it,
    returning a dictionary mapping the case ids affected to the
    couch case document objects
    """
    # have to apply the deprecations before the updates
    sorted_forms = sorted(xforms, key=lambda f: 0 if is_deprecation(f) else 1)
    touched_cases = {}
    for xform in sorted_forms:
        for case_update in get_case_updates(xform):
            case_doc = _get_or_update_model(case_update, xform, case_db)
            touched_cases[case_doc['_id']] = case_doc
            if case_doc:
                # todo: legacy behavior, should remove after new case processing
                # is fully enabled.
                if xform._id not in case_doc.xform_ids:
                    case_doc.xform_ids.append(xform.get_id)
            else:
                logging.error(
                    "XForm %s had a case block that wasn't able to create a case! "
                    "This usually means it had a missing ID" % xform.get_id
                )

    # once we've gotten through everything, validate all indices
    # and check for new dirtiness flags
    def _validate_indices(case):
        dirtiness_flags = []
        is_dirty = False
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
                else:
                    if referenced_case.owner_id != case.owner_id:
                        is_dirty = True
        if is_dirty:
            dirtiness_flags.append(DirtinessFlag(case._id, case.owner_id))
        return dirtiness_flags

    def _get_dirtiness_flags_for_child_cases(domain, cases):
        child_cases = get_reverse_indexed_cases(domain, [c['_id'] for c in cases])
        case_owner_map = dict((case._id, case.owner_id) for case in cases)
        for child_case in child_cases:
            for index in child_case.indices:
                if (index.referenced_id in case_owner_map
                        and child_case.owner_id != case_owner_map[index.referenced_id]):
                    yield DirtinessFlag(child_case._id, child_case.owner_id)

    dirtiness_flags = [flag for case in touched_cases.values() for flag in _validate_indices(case)]
    domain = getattr(case_db, 'domain', None)
    track_cleanliness = should_track_cleanliness(domain)
    if track_cleanliness:
        # only do this extra step if the toggle is enabled since we know we aren't going to
        # care about the dirtiness flags otherwise.
        dirtiness_flags += list(_get_dirtiness_flags_for_child_cases(domain, touched_cases.values()))

    return CaseProcessingResult(domain, touched_cases.values(), dirtiness_flags, track_cleanliness)


def _get_or_update_model(case_update, xform, case_db):
    """
    Gets or updates an existing case, based on a block of data in a
    submitted form.  Doesn't save anything.
    """
    case = case_db.get(case_update.id)
    if case is None:
        case = CommCareCase.from_case_update(case_update, xform)
        case_db.set(case['_id'], case)
        return case
    else:
        case.update_from_case_update(case_update, xform, case_db.get_cached_forms())
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


CaseBlockWithPath = namedtuple('CaseBlockWithPath', ['caseblock', 'path'])


def extract_case_blocks(doc, include_path=False):
    """
    Extract all case blocks from a document, returning an array of dictionaries
    with the data in each case.

    The json returned is not normalized for casexml version;
    for that get_case_updates is better.

    if `include_path` is True then instead of returning just the case block it will
    return a dict with the following structure:

    {
       "caseblock": caseblock
       "path": ["form", "path", "to", "block"]
    }

    Repeat nodes will all share the same path.
    """
    if isinstance(doc, XFormInstance):
        doc = doc.form

    return [struct if include_path else struct.caseblock for struct in _extract_case_blocks(doc)]


def _extract_case_blocks(data, path=None):
    """
    helper for extract_case_blocks

    data must be json representing a node in an xform submission
    """
    path = path or []
    if isinstance(data, list):
        for item in data:
            for case_block in _extract_case_blocks(item, path=path):
                yield case_block
    elif isinstance(data, dict) and not is_device_report(data):
        for key, value in data.items():
            new_path = path + [key]
            if const.CASE_TAG == key:
                # it's a case block! Stop recursion and add to this value
                if isinstance(value, list):
                    case_blocks = value
                else:
                    case_blocks = [value]

                for case_block in case_blocks:
                    if has_case_id(case_block):
                        yield CaseBlockWithPath(caseblock=case_block, path=path)
            else:
                for case_block in _extract_case_blocks(value, path=new_path):
                    yield case_block


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
