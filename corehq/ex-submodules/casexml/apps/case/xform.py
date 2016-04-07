from collections import namedtuple
import logging

from couchdbkit import ResourceNotFound
from django.db.models import Q
from casexml.apps.case.const import UNOWNED_EXTENSION_OWNER_ID, CASE_INDEX_EXTENSION
from casexml.apps.case.dbaccessors import get_extension_chain
from casexml.apps.case.signals import cases_received
from casexml.apps.case.util import validate_phone_datetime
from casexml.apps.phone.cleanliness import should_create_flags_on_submission
from casexml.apps.phone.models import OwnershipCleanlinessFlag
from corehq.toggles import LOOSE_SYNC_TOKEN_VALIDATION, EXTENSION_CASES_SYNC_ENABLED
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from couchforms.models import XFormInstance
from casexml.apps.case.exceptions import (
    NoDomainProvided,
)
from django.conf import settings
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
    def __init__(self, domain, cases, dirtiness_flags, extensions_to_close=None):
        self.domain = domain
        self.cases = cases
        self.dirtiness_flags = dirtiness_flags
        if extensions_to_close is None:
            extensions_to_close = set()
        self.extensions_to_close = extensions_to_close

    def get_clean_owner_ids(self):
        dirty_flags = self.get_flags_to_save()
        return {c.owner_id for c in self.cases if c.owner_id and c.owner_id not in dirty_flags}

    def set_cases(self, cases):
        self.cases = cases

    def get_flags_to_save(self):
        return {f.owner_id: f.case_id for f in self.dirtiness_flags}

    def close_extensions(self):
        from casexml.apps.case.cleanup import close_cases
        extensions_to_close = list(self.extensions_to_close)
        if extensions_to_close:
            return close_cases(list(self.extensions_to_close), self.domain, SYSTEM_USER_ID)

    def commit_dirtiness_flags(self):
        """
        Updates any dirtiness flags in the database.
        """
        if self.domain:
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


def process_cases_with_casedb(xforms, case_db, config=None):
    config = config or CaseProcessingConfig()
    case_processing_result = _get_or_update_cases(xforms, case_db)
    cases = case_processing_result.cases
    xform = xforms[0]

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
            'for form %s: %s' % (xform.form_id, e)
        )

    for case in cases:
        case_db.post_process_case(case, xform)
        case_db.mark_changed(case)

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
    domain = getattr(case_db, 'domain', None)
    touched_cases = FormProcessorInterface(domain).get_cases_from_forms(case_db, xforms)

    # once we've gotten through everything, validate all indices
    # and check for new dirtiness flags
    def _validate_indices(case):
        if case.indices:
            for index in case.indices:
                # call get and not doc_exists to force domain checking
                # see CaseDbCache._validate_case
                referenced_case = case_db.get(index.referenced_id)
                if not referenced_case:
                    # just log, don't raise an error or modify the index
                    logging.error(
                        "Case '%s' references non-existent case '%s'",
                        case.case_id,
                        index.referenced_id,
                    )

    def _get_dirtiness_flags_for_outgoing_indices(case, tree_owners=None):
        """ if the outgoing indices touch cases owned by another user this cases owner is dirty """
        if tree_owners is None:
            tree_owners = set()

        extension_indices = [index for index in case.indices if index.relationship == CASE_INDEX_EXTENSION]

        unowned_host_cases = []
        for index in extension_indices:
            host_case = case_db.get(index.referenced_id)
            if (
                host_case
                and host_case.owner_id == UNOWNED_EXTENSION_OWNER_ID
                and host_case not in unowned_host_cases
            ):
                unowned_host_cases.append(host_case)

        owner_ids = {case_db.get(index.referenced_id).owner_id
                     for index in case.indices if case_db.get(index.referenced_id)} | tree_owners
        potential_clean_owner_ids = owner_ids | set([UNOWNED_EXTENSION_OWNER_ID])
        more_than_one_owner_touched = len(owner_ids) > 1
        touches_different_owner = len(owner_ids) == 1 and case.owner_id not in potential_clean_owner_ids

        if (more_than_one_owner_touched or touches_different_owner):
            yield DirtinessFlag(case.case_id, case.owner_id)
            if extension_indices:
                # If this case is an extension, each of the touched cases is also dirty
                for index in case.indices:
                    referenced_case = case_db.get(index.referenced_id)
                    yield DirtinessFlag(referenced_case.case_id, referenced_case.owner_id)

        if case.owner_id != UNOWNED_EXTENSION_OWNER_ID:
            tree_owners.add(case.owner_id)
        for unowned_host_case in unowned_host_cases:
            # A host case of this extension is unowned, which means it could potentially touch an owned case
            # Check these unowned cases' outgoing indices and mark dirty if appropriate
            for dirtiness_flag in _get_dirtiness_flags_for_outgoing_indices(unowned_host_case,
                                                                            tree_owners=tree_owners):
                yield dirtiness_flag

    def _get_dirtiness_flags_for_child_cases(cases):
        child_cases = case_db.get_reverse_indexed_cases([c.case_id for c in cases])
        case_owner_map = dict((case.case_id, case.owner_id) for case in cases)
        for child_case in child_cases:
            for index in child_case.indices:
                if (index.referenced_id in case_owner_map
                        and child_case.owner_id != case_owner_map[index.referenced_id]):
                    yield DirtinessFlag(child_case.case_id, child_case.owner_id)

    def _get_dirtiness_flags_for_reassigned_case(case_metas):
        # for reassigned cases, we mark them temporarily dirty to allow phones to sync
        # the latest changes. these will get cleaned up when the weekly rebuild triggers
        for case_update_meta in case_metas:
            if _is_change_of_ownership(case_update_meta.previous_owner_id, case_update_meta.case.owner_id):
                yield DirtinessFlag(case_update_meta.case.case_id, case_update_meta.previous_owner_id)

    dirtiness_flags = []
    extensions_to_close = set()

    # process the temporary dirtiness flags first so that any hints for real dirtiness get overridden
    dirtiness_flags += list(_get_dirtiness_flags_for_reassigned_case(touched_cases.values()))
    for case_update_meta in touched_cases.values():
        _validate_indices(case_update_meta.case)
        extensions_to_close = extensions_to_close | get_extensions_to_close(case_update_meta.case, domain)
        dirtiness_flags += list(_get_dirtiness_flags_for_outgoing_indices(case_update_meta.case))
    dirtiness_flags += list(_get_dirtiness_flags_for_child_cases([meta.case for meta in touched_cases.values()]))

    return CaseProcessingResult(
        domain,
        [update.case for update in touched_cases.values()],
        dirtiness_flags,
        extensions_to_close
    )


def _is_change_of_ownership(previous_owner_id, next_owner_id):
    return (
        previous_owner_id
        and previous_owner_id != UNOWNED_EXTENSION_OWNER_ID
        and previous_owner_id != next_owner_id
    )


def get_extensions_to_close(case, domain):
    outgoing_extension_indices = [index.relationship for index in case.indices
                                  if index.relationship == CASE_INDEX_EXTENSION]
    if not outgoing_extension_indices and case.closed and EXTENSION_CASES_SYNC_ENABLED.enabled(domain):
        return get_extension_chain([case.case_id], domain)
    else:
        return set()


def is_device_report(doc):
    """exclude device reports"""
    device_report_xmlns = "http://code.javarosa.org/devicereport"
    def _from_form_dict(doc):
        return isinstance(doc, dict) and "@xmlns" in doc and doc["@xmlns"] == device_report_xmlns
    def _from_xform_instance(doc):
        return getattr(doc, 'xmlns', None) == device_report_xmlns

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
        form = doc.to_json()['form']
    elif isinstance(doc, dict):
        form = doc
    else:
        form = doc.form_data

    return [struct if include_path else struct.caseblock for struct in _extract_case_blocks(form)]


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
                        validate_phone_datetime(
                            case_block.get('@date_modified'), none_ok=True)
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
    Returns a list of CommCareCase or CommCareCaseSQL given a JSON
    representation of an XFormInstance
    """
    from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
    from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
    case_ids = get_case_ids_from_form(xform)
    domain = get_and_check_xform_domain(xform)
    case_accessor = CaseAccessors(domain)
    if domain is None:
        assert case_accessor.db_accessor == CaseAccessorCouch
    return case_accessor.get_cases(list(case_ids))
