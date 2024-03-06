from collections import namedtuple
from itertools import groupby

import itertools
from casexml.apps.case.const import UNOWNED_EXTENSION_OWNER_ID
from casexml.apps.case.util import validate_phone_datetime, prune_previous_log
from corehq import toggles
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import CommCareCaseIndex
from corehq.util.soft_assert import soft_assert
from casexml.apps.case.exceptions import InvalidCaseIndex, IllegalCaseId

from casexml.apps.case import const
from casexml.apps.case.xml.parser import case_id_from_block, case_update_from_block
from custom.covid.casesync import get_ush_extension_cases_to_close

_soft_assert = soft_assert(to="{}@{}.com".format('skelly', 'dimagi'), notify_admins=True)


class CaseProcessingResult(object):
    """
    Lightweight class used to collect results of case processing
    """

    def __init__(self, domain, cases):
        self.domain = domain
        self.cases = cases

    def set_cases(self, cases):
        self.cases = cases


def process_cases_with_casedb(xforms, case_db):
    case_processing_result = _get_or_update_cases(xforms, case_db)
    cases = case_processing_result.cases
    xform = xforms[0]

    _update_sync_logs(xform, cases)

    for case in cases:
        case_db.post_process_case(case, xform)
        case_db.mark_changed(case)

    case_processing_result.set_cases(cases)
    return case_processing_result


def _update_sync_logs(xform, cases):
    # handle updating the sync records for apps that use sync mode
    relevant_log = xform.get_sync_token()
    if relevant_log:
        changed = relevant_log.update_phone_lists(xform, cases)
        changed |= prune_previous_log(relevant_log)
        if changed:
            relevant_log.save()


def _get_or_update_cases(xforms, case_db):
    """
    Given an xform document, update any case blocks found within it,
    returning a dictionary mapping the case ids affected to the
    couch case document objects
    """
    domain = getattr(case_db, 'domain', None)
    touched_cases = FormProcessorInterface(domain).get_cases_from_forms(case_db, xforms)
    _validate_indices(case_db, touched_cases.values())
    return CaseProcessingResult(
        domain,
        [update.case for update in touched_cases.values()],
    )


def _validate_indices(case_db, case_updates):
    for case_update in case_updates:
        if not case_update.index_change:
            continue

        case = case_update.case
        if case.indices:
            for index in case.indices:
                if not index.is_deleted:
                    try:
                        # call get and not doc_exists to force domain checking
                        # see CaseDbCache._validate_case
                        referenced_case = case_db.get(index.referenced_id)
                        invalid = referenced_case is None
                    except IllegalCaseId:
                        invalid = True
                else:
                    invalid = False
                if invalid:
                    # fail hard on invalid indices
                    from looseversion import LooseVersion
                    if case_db.cached_xforms and case_db.domain != 'commcare-tests':
                        xform = case_db.cached_xforms[0]
                        if xform.metadata and xform.metadata.commcare_version:
                            commcare_version = xform.metadata.commcare_version
                            _soft_assert(
                                commcare_version < LooseVersion("2.39"),
                                "Invalid Case Index in CC version >= 2.39", {
                                    'domain': case_db.domain,
                                    'xform_id': xform.form_id,
                                    'missing_case_id': index.referenced_id,
                                    'version': str(commcare_version)
                                }
                            )
                    raise InvalidCaseIndex(
                        "Case '%s' references non-existent case '%s'" % (case.case_id, index.referenced_id)
                    )


def _is_change_of_ownership(previous_owner_id, next_owner_id):
    return (
        previous_owner_id
        and previous_owner_id != UNOWNED_EXTENSION_OWNER_ID
        and previous_owner_id != next_owner_id
    )


def close_extension_cases(case_db, cases, device_id, synctoken_id):
    from casexml.apps.case.cleanup import close_cases
    extensions_to_close = get_all_extensions_to_close(case_db.domain, cases)
    extensions_to_close = case_db.filter_closed_extensions(list(extensions_to_close))
    if extensions_to_close:
        return close_cases(
            extensions_to_close,
            case_db.domain,
            SYSTEM_USER_ID,
            device_id,
            case_db,
            synctoken_id
        )


def get_all_extensions_to_close(domain, cases):
    if toggles.EXTENSION_CASES_SYNC_ENABLED.enabled(domain):
        if toggles.USH_DONT_CLOSE_PATIENT_EXTENSIONS.enabled(domain):
            return get_ush_extension_cases_to_close(domain, cases)
        return get_extensions_to_close(domain, cases)
    return set()


def get_extensions_to_close(domain, cases):
    case_ids = [case.case_id for case in cases if case.closed]
    return CommCareCaseIndex.objects.get_extension_chain(domain, case_ids, include_closed=False)


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
    return a namedtuple with the following attributes:

       caseblock: case block
       path: ["form", "path", "to", "block"]

    Repeat nodes will all share the same path.
    """
    if isinstance(doc, dict):
        form = doc
    else:
        form = doc.form_data

    return list(_extract_case_blocks(form, [] if include_path else None))


def _extract_case_blocks(data, path=None, form_id=Ellipsis):
    """
    helper for extract_case_blocks

    data must be json representing a node in an xform submission
    """
    from corehq.form_processor.utils import extract_meta_instance_id
    if form_id is Ellipsis:
        form_id = extract_meta_instance_id(data)

    if isinstance(data, list):
        for item in data:
            yield from _extract_case_blocks(item, path, form_id=form_id)
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
                        validate_phone_datetime(
                            case_block.get('@date_modified'), none_ok=True, form_id=form_id
                        )
                        if path is None:
                            yield case_block
                        else:
                            yield CaseBlockWithPath(caseblock=case_block, path=path)
            else:
                new_path = None if path is None else path + [key]
                yield from _extract_case_blocks(value, new_path, form_id=form_id)


class TempCaseBlockCache:
    def __init__(self):
        self.cache = {}

    def get_case_blocks(self, form):
        try:
            case_blocks = self.cache[form.form_id]
        except KeyError:
            case_blocks = extract_case_blocks(form)
            self.cache[form.form_id] = case_blocks
        return case_blocks


def get_case_updates(xform, for_case=None, case_block_cache=None):
    if not xform:
        return []

    if case_block_cache:
        case_blocks = case_block_cache.get_case_blocks(xform)
    else:
        case_blocks = extract_case_blocks(xform)
    updates = [case_update_from_block(cb) for cb in case_blocks]

    if for_case:
        updates = [update for update in updates if update.id == for_case]
        by_case_id = [(for_case, updates)]
    else:
        updates = sorted(
            updates,
            key=lambda update: update.id
        )
        by_case_id = groupby(updates, lambda update: update.id)

    return list(itertools.chain(
        *[order_updates(updates) for case_id, updates in by_case_id]
    ))


def order_updates(case_updates):
    """Order case updates for a single case according to the actions
    they contain.

    This is to ensure create actions are applied before update actions.
    """
    return sorted(case_updates, key=_update_order_index)


def _update_order_index(update):
    """
    Consistent order index based on the types of actions in the update.
    """
    return min(
        const.CASE_ACTIONS.index(action.action_type_slug)
        for action in update.actions
    )


def get_case_ids_from_form(xform):
    from corehq.form_processor.parsers.ledgers.form import get_case_ids_from_stock_transactions
    case_ids = set(case_id_from_block(b) for b in extract_case_blocks(xform))
    if xform:
        case_ids.update(get_case_ids_from_stock_transactions(xform))
    return case_ids
