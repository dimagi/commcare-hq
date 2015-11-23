from collections import namedtuple

from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.models import CommCareCaseAction
from casexml.apps.case.xform import is_device_report
from casexml.apps.case.xml.parser import AbstractAction


CaseActionIntent = namedtuple('CaseActionIntent', ['case_id', 'form_id', 'is_deprecation', 'action'])
StockFormActions = namedtuple('StockFormActions', ['stock_report_helpers', 'case_action_intents'])


def get_stock_actions(xform):
    """
    Pulls out the ledger blocks and case action intents from a form and returns them
    in a StockFormActions object.

    The stock_report_helpers are StockReportHelper objects, which are basically parsed commtrack actions.
    They should only affect ledger data.

    The case_action_intents are the actions that should be applied to the case, and should not contain
    any ledger data. These are just marker actions that can be used in looking up a case's forms or
    in rebuilding it.
    """
    from corehq.apps.commtrack.parsing import unpack_commtrack
    if is_device_report(xform):
        return _empty_actions()

    stock_report_helpers = list(unpack_commtrack(xform))
    transaction_helpers = [
        transaction_helper
        for stock_report_helper in stock_report_helpers
        for transaction_helper in stock_report_helper.transactions
    ]
    if not transaction_helpers:
        return _empty_actions()

    case_action_intents = _get_case_action_intents(xform, transaction_helpers)
    return StockFormActions(stock_report_helpers, case_action_intents)


def _empty_actions():
    return StockFormActions([], [])


def _get_case_action_intents(xform, transaction_helpers):
    # list of cases that had stock reports in the form
    case_ids = list(set(transaction_helper.case_id
                        for transaction_helper in transaction_helpers))

    user_id = xform.metadata.userID
    submit_time = xform.received_on
    case_action_intents = []
    for case_id in case_ids:
        if xform.is_deprecated:
            case_action_intents.append(CaseActionIntent(
                case_id=case_id, form_id=xform.orig_id, is_deprecation=True, action=None
            ))
        else:
            # todo: convert to CaseTransaction object
            case_action = CommCareCaseAction.from_parsed_action(
                submit_time, user_id, xform, AbstractAction(CASE_ACTION_COMMTRACK)
            )
            case_action_intents.append(CaseActionIntent(
                case_id=case_id, form_id=xform.form_id, is_deprecation=False, action=case_action
            ))
    return case_action_intents

