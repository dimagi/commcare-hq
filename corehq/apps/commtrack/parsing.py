"""
This file is dedicated to parsing ledger xml as documented at
https://github.com/dimagi/commcare/wiki/ledgerxml

The quirks of ledger xml are outlined as follows.

There are two **Ledger Report Types**, 'balance' and 'transfer':

    <balance entity-id=""/>
and
    <transfer src="" dest="" type=""/>

There are also two **Ledger Report Formats**, 'individual' and 'per-entry'.

- Individual Ledger Balance:

    <balance xmlns="http://commcarehq.org/ledger/v1" entity-id="" date="" section-id="">
        <entry id="" quantity="" /> <!--multiple-->
    </balance>

  parsed into JSON as

    {"@xmlns": "http://commcarehq.org/ledger/v1", "@entity-id": "",
     "@date": "", "@section-id": "",
     "entry": [{"@id": "", "@quantity": ""}]}

- Per-Entry Ledger Balance:

    <balance xmlns="http://commcarehq.org/ledger/v1" entity-id="" date="">
        <entry id=""> <!--multiple-->
            <value section-id="" quantity=""/> <!-- multiple -->
        </entry>
    </balance>

  parsed into JSON as

    {"@xmlns": "http://commcarehq.org/ledger/v1", "@entity-id": "",
     "@date": "",
     "entry": [{"@id": "", "value": [{"@section-id: "", "@quantity": ""},
               ...]}]}

Conceptually, both formats produce a list of transactions:

    (entity_id="", date="", section_id="", entry_id="", quantity="")
    ...

but Per-Entry lets you have many different section_ids among the transactions.

"""
from collections import namedtuple
from decimal import Decimal
import logging
import datetime
from casexml.apps.stock import const as stockconst
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from corehq.apps.commtrack import const
from corehq.apps.commtrack.exceptions import InvalidDate
from corehq.apps.commtrack.models import StockReportHelper, \
    StockTransactionHelper
from couchforms.models import XFormInstance
from couchforms.util import adjust_datetimes
from xml2json.lib import convert_xml_to_json


LedgerInstruction = namedtuple(
    'LedgerInstruction',
    ['date', 'section_id', 'entry_id', 'quantity',
     # for balance instructions
     'entity_id',
     # for transfer instructions
     'src', 'dest', 'type']
)


class LedgerFormat(object):
    individual = object()
    per_entry = object()


def should_be_a_list(obj_or_list):
    if obj_or_list is None:
        return []
    elif isinstance(obj_or_list, list):
        return obj_or_list
    else:
        return [obj_or_list]


def unpack_commtrack(xform):
    form_xml = xform.get_xml_element()
    commtrack_node_names = ('{%s}balance' % COMMTRACK_REPORT_XMLNS,
                            '{%s}transfer' % COMMTRACK_REPORT_XMLNS)

    def commtrack_nodes(node):
        for child in node:
            if child.tag in commtrack_node_names:
                yield child
            else:
                for e in commtrack_nodes(child):
                    yield e

    for elem in commtrack_nodes(form_xml):
        report_type, ledger_json = convert_xml_to_json(
            elem, last_xmlns=COMMTRACK_REPORT_XMLNS)

        # apply the same datetime & string conversions
        # that would be applied to XFormInstance.form
        adjust_datetimes(ledger_json)
        ledger_json = XFormInstance({'form': ledger_json}).form

        yield ledger_json_to_stock_report_helper(
            xform, report_type, ledger_json)


def ledger_json_to_stock_report_helper(form, report_type, ledger_json):
    domain = form.domain
    # figure out what kind of block we're dealing with
    if ledger_json.get('@section-id'):
        ledger_format = LedgerFormat.individual
    else:
        ledger_format = LedgerFormat.per_entry

    # helper functions
    def get_date():
        timestamp = ledger_json.get('@date') or form.received_on
        if type(timestamp) is datetime.date:
            timestamp = datetime.datetime.combine(timestamp, datetime.time())

        if not isinstance(timestamp, (datetime.datetime)):
            raise InvalidDate("{} has invalid @date".format(ledger_json))
        return timestamp

    def make_transaction_helper(ledger_instruction, action, case_id):
        subaction = ledger_instruction.type
        return StockTransactionHelper(
            # domain is a closure variable
            domain=domain,
            timestamp=ledger_instruction.date,
            product_id=ledger_instruction.entry_id,
            quantity=ledger_instruction.quantity,
            action=action,
            case_id=case_id,
            section_id=ledger_instruction.section_id,
            subaction=subaction if subaction and subaction != action else None,
            location_id=None,
        )

    # details of transaction generation
    # depend on whether it's a balance or a transfer
    if report_type == stockconst.REPORT_TYPE_BALANCE:
        def get_transaction_helpers(ledger_instruction):

            case_id = ledger_instruction.entity_id
            yield make_transaction_helper(
                ledger_instruction,
                action=(const.StockActions.STOCKONHAND
                        if ledger_instruction.quantity > 0
                        else const.StockActions.STOCKOUT),
                case_id=case_id,
            )
    elif report_type == stockconst.REPORT_TYPE_TRANSFER:
        def get_transaction_helpers(ledger_instruction):
            src = ledger_instruction.src
            dest = ledger_instruction.dest
            assert src or dest
            if src is not None:
                yield make_transaction_helper(
                    ledger_instruction,
                    action=const.StockActions.CONSUMPTION, case_id=src)
            if dest is not None:
                yield make_transaction_helper(
                    ledger_instruction,
                    action=const.StockActions.RECEIPTS, case_id=dest)
    else:
        raise ValueError()

    def get_quantity_or_none(value, section_id):
        try:
            return Decimal(str(float(value.get('@quantity'))))
        except (ValueError, TypeError):
            logging.error((
                "Non-numeric quantity submitted on domain %s for "
                "a %s ledger" % (domain, section_id)
            ))
            return None

    timestamp = get_date()
    ledger_instructions = []
    if ledger_format == LedgerFormat.individual:
        # this is @date, @section-id, etc.
        # but also balance/transfer specific attributes:
        # @entity-id/@src,@dest
        section_id = ledger_json.get('@section-id')
        top_level_attributes = {
            'date': timestamp,
            'section_id': section_id,
            'entity_id': ledger_json.get('@entity-id'),
            'src': ledger_json.get('@src'),
            'dest': ledger_json.get('@dest'),
            'type': ledger_json.get('@type'),
        }

        product_entries = should_be_a_list(ledger_json.get('entry'))
        for product_entry in product_entries:
            # product_entry looks like
            # {"@id": "", "@quantity": ""}
            t = {}
            t.update(top_level_attributes)
            t.update({'entry_id': product_entry.get('@id'),
                      'quantity': get_quantity_or_none(product_entry,
                                                       section_id)})
            ledger_instructions.append(LedgerInstruction(**t))
    else:
        top_level_attributes = {
            'date': timestamp,
            'entity_id': ledger_json.get('@entity-id'),
            'src': ledger_json.get('@src'),
            'dest': ledger_json.get('@dest'),
            'type': ledger_json.get('@type'),
        }

        product_entries = should_be_a_list(ledger_json.get('entry'))
        for product_entry in product_entries:
            # product_entry looks like
            # {"@id": "", 'value': [...]}
            for value in should_be_a_list(product_entry.get('value')):
                # value looks like
                # {"@section-id: "", "@quantity": ""}
                t = {}
                section_id = value.get('@section-id')
                t.update(top_level_attributes)
                t.update({'entry_id': product_entry.get('@id')})
                t.update({'quantity': get_quantity_or_none(value, section_id),
                          'section_id': section_id})
                ledger_instructions.append(LedgerInstruction(**t))

    # filter out ones where quantity is None
    # todo: is this really the behavior we want when quantity=""?
    ledger_instructions = [
        ledger_instruction
        for ledger_instruction in ledger_instructions
        if ledger_instruction.quantity is not None
    ]

    transaction_helpers = [
        transaction_helper
        for ledger_instruction in ledger_instructions
        for transaction_helper in get_transaction_helpers(ledger_instruction)
    ]

    return StockReportHelper.make_from_form(form, timestamp, report_type, transaction_helpers)
