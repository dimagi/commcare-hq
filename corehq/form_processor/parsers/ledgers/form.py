from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
import datetime
from decimal import Decimal
import logging

import iso8601
from django.utils.translation import ugettext as _

from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.models import CommCareCaseAction
from casexml.apps.case.xform import is_device_report
from casexml.apps.case.xml.parser import AbstractAction
from casexml.apps.stock import const as stockconst
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from corehq.apps.commtrack import const
from corehq.apps.commtrack.exceptions import InvalidDate
from corehq.form_processor.parsers.ledgers.helpers import StockTransactionHelper, StockReportHelper, \
    UniqueLedgerReference
from corehq.form_processor.utils.xform import adjust_text_to_datetime
from xml2json.lib import convert_xml_to_json


class LedgerFormat(object):
    """This object is just used to represent these two constants"""
    INDIVIDUAL = object()
    PER_ENTRY = object()


class CaseActionIntent(namedtuple('CaseActionIntent',
                                  ['case_id', 'form_id', 'is_deprecation', 'action_type', 'form'])):

    def get_couch_action(self):
        assert self.action_type == CASE_ACTION_COMMTRACK
        return CommCareCaseAction.from_parsed_action(
            date=self.form.received_on,
            user_id=self.form.metadata.userID,
            xformdoc=self.form,
            action=AbstractAction(self.action_type),
        )


StockFormActions = namedtuple('StockFormActions', ['stock_report_helpers', 'case_action_intents'])
LedgerInstruction = namedtuple(
    'LedgerInstruction',
    ['domain', 'date', 'section_id', 'entry_id', 'quantity',
     # for balance instructions
     'entity_id',
     # for transfer instructions
     'src', 'dest', 'type']
)


def get_case_ids_from_stock_transactions(xform):
    return {
        transaction_helper.case_id
        for stock_report_helper in get_all_stock_report_helpers_from_form(xform)
        for transaction_helper in stock_report_helper.transactions
    }


def get_ledger_references_from_stock_transactions(xform):
    return {
        UniqueLedgerReference(tx_helper.case_id, tx_helper.section_id, tx_helper.product_id)
        for stock_report_helper in get_all_stock_report_helpers_from_form(xform)
        for tx_helper in stock_report_helper.transactions
    }


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
    if is_device_report(xform):
        return _empty_actions()

    stock_report_helpers = list(get_all_stock_report_helpers_from_form(xform))
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
    case_action_intents = []
    for case_id in case_ids:
        if xform.is_deprecated:
            case_action_intents.append(CaseActionIntent(
                case_id=case_id, form_id=xform.orig_id, is_deprecation=True, action_type=None, form=xform,
            ))
        else:
            case_action_intents.append(CaseActionIntent(
                case_id=case_id,
                form_id=xform.form_id,
                is_deprecation=False,
                action_type=CASE_ACTION_COMMTRACK,
                form=xform
            ))
    return case_action_intents


def get_all_stock_report_helpers_from_form(xform):
    """
    Given an instance of an AbstractXFormInstance, extract the ledger actions and convert
    them to StockReportHelper objects.
    """
    if xform.get_xml_element is None:
        # ESXFormInstance (has a weird API)
        raise MissingFormXml(xform.form_id)
    form_xml = xform.get_xml_element()
    if form_xml is None:
        # HACK should be raised by xform.get_xml_element()
        raise MissingFormXml(xform.form_id)
    commtrack_node_names = ('{%s}balance' % COMMTRACK_REPORT_XMLNS,
                            '{%s}transfer' % COMMTRACK_REPORT_XMLNS)

    def _extract_ledger_nodes_from_xml(node):
        """
        Goes through a parsed XML document and recursively pulls out any ledger XML blocks.
        """
        for child in node:
            if child.tag in commtrack_node_names:
                yield child
            else:
                for e in _extract_ledger_nodes_from_xml(child):
                    yield e

    for elem in _extract_ledger_nodes_from_xml(form_xml):
        report_type, ledger_json = convert_xml_to_json(elem, last_xmlns=COMMTRACK_REPORT_XMLNS)
        if ledger_json.get('@date'):
            try:
                ledger_json['@date'] = adjust_text_to_datetime(ledger_json['@date'])
            except iso8601.ParseError:
                pass
        yield _ledger_json_to_stock_report_helper(xform, report_type, ledger_json)


def _ledger_json_to_stock_report_helper(form, report_type, ledger_json):
    domain = form.domain
    # figure out what kind of block we're dealing with
    if ledger_json.get('@section-id'):
        ledger_format = LedgerFormat.INDIVIDUAL
    else:
        ledger_format = LedgerFormat.PER_ENTRY

    # details of transaction generation
    # depend on whether it's a balance or a transfer
    if report_type not in (stockconst.REPORT_TYPE_BALANCE, stockconst.REPORT_TYPE_TRANSFER):
        raise ValueError(_('Invalid stock report type {}!'.format(report_type)))

    timestamp = _get_and_validate_date(ledger_json, form)
    common_attributes = {
        'domain': domain,
        'date': timestamp,
    }
    if ledger_format == LedgerFormat.INDIVIDUAL:
        ledger_instructions = _get_ledger_instructions_from_individual_format(ledger_json, common_attributes)
    else:
        ledger_instructions = _get_ledger_instructions_from_per_entry_format(ledger_json, common_attributes)

    # filter out ones where quantity is None
    # todo: is this really the behavior we want when quantity=""?
    ledger_instructions = [
        ledger_instruction
        for ledger_instruction in ledger_instructions
        if ledger_instruction.quantity is not None
    ]

    helper_generator_fn = {
        stockconst.REPORT_TYPE_BALANCE: _get_transaction_helpers_from_balance_instruction,
        stockconst.REPORT_TYPE_TRANSFER: _get_transaction_helpers_from_transfer_instruction,
    }[report_type]
    transaction_helpers = [
        transaction_helper
        for ledger_instruction in ledger_instructions
        for transaction_helper in helper_generator_fn(ledger_instruction)
    ]
    return StockReportHelper.make_from_form(form, timestamp, report_type, transaction_helpers)


def _get_ledger_instructions_from_individual_format(ledger_json, common_attributes):
    # this is @date, @section-id, etc.
    # but also balance/transfer specific attributes:
    # @entity-id/@src,@dest
    section_id = ledger_json.get('@section-id')
    top_level_attributes = {
        'section_id': section_id,
        'entity_id': ledger_json.get('@entity-id'),
        'src': ledger_json.get('@src'),
        'dest': ledger_json.get('@dest'),
        'type': ledger_json.get('@type'),
    }
    top_level_attributes.update(common_attributes)
    product_entries = _coerce_to_list(ledger_json.get('entry'))
    for product_entry in product_entries:
        # product_entry looks like
        # {"@id": "", "@quantity": ""}
        t = {}
        t.update(top_level_attributes)
        t.update({'entry_id': product_entry.get('@id'),
                  'quantity': _get_quantity_or_none(product_entry, section_id, common_attributes['domain'])})
        yield LedgerInstruction(**t)


def _get_ledger_instructions_from_per_entry_format(ledger_json, common_attributes):
    top_level_attributes = {
        'entity_id': ledger_json.get('@entity-id'),
        'src': ledger_json.get('@src'),
        'dest': ledger_json.get('@dest'),
        'type': ledger_json.get('@type'),
    }
    top_level_attributes.update(common_attributes)

    product_entries = _coerce_to_list(ledger_json.get('entry'))
    for product_entry in product_entries:
        # product_entry looks like
        # {"@id": "", 'value': [...]}
        for value in _coerce_to_list(product_entry.get('value')):
            # value looks like
            # {"@section-id: "", "@quantity": ""}
            t = {}
            section_id = value.get('@section-id')
            t.update(top_level_attributes)
            t.update({'entry_id': product_entry.get('@id')})
            t.update({'quantity': _get_quantity_or_none(value, section_id, common_attributes['domain']),
                      'section_id': section_id})
            yield LedgerInstruction(**t)


def _get_transaction_helpers_from_balance_instruction(ledger_instruction):
    case_id = ledger_instruction.entity_id
    yield _make_transaction_helper(
        ledger_instruction,
        action=(const.StockActions.STOCKONHAND
                if ledger_instruction.quantity > 0
                else const.StockActions.STOCKOUT),
        case_id=case_id,
    )


def _get_transaction_helpers_from_transfer_instruction(ledger_instruction):
    src = ledger_instruction.src
    dest = ledger_instruction.dest
    if not (src or dest):
        raise IllegalCaseId(_("Can't specify a transaction block with no src or dest case"))
    if src is not None:
        yield _make_transaction_helper(
            ledger_instruction,
            action=const.StockActions.CONSUMPTION, case_id=src)
    if dest is not None:
        yield _make_transaction_helper(
            ledger_instruction,
            action=const.StockActions.RECEIPTS, case_id=dest)


def _make_transaction_helper(ledger_instruction, action, case_id):
    subaction = ledger_instruction.type
    return StockTransactionHelper(
        domain=ledger_instruction.domain,
        timestamp=ledger_instruction.date,
        product_id=ledger_instruction.entry_id,
        quantity=ledger_instruction.quantity,
        action=action,
        case_id=case_id,
        section_id=ledger_instruction.section_id,
        subaction=subaction if subaction and subaction != action else None,
        location_id=None,
    )


def _get_and_validate_date(ledger_json, form):
    timestamp = ledger_json.get('@date') or form.received_on
    if type(timestamp) is datetime.date:
        timestamp = datetime.datetime.combine(timestamp, datetime.time())

    if not isinstance(timestamp, (datetime.datetime)):
        raise InvalidDate("{} has invalid @date".format(ledger_json))
    return timestamp


def _get_quantity_or_none(value, section_id, domain):
    try:
        return Decimal(str(float(value.get('@quantity'))))
    except (ValueError, TypeError):
        logging.error((
            "Non-numeric quantity submitted on domain %s for "
            "a %s ledger" % (domain, section_id)
        ))
        return None


def _coerce_to_list(obj_or_list):
    if obj_or_list is None:
        return []
    elif isinstance(obj_or_list, list):
        return obj_or_list
    else:
        return [obj_or_list]


class MissingFormXml(Exception):
    pass
