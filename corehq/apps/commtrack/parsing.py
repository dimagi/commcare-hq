from decimal import Decimal
import logging
from casexml.apps.stock import const as stockconst
from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import StockReportHelper, \
    StockTransactionHelper
from dimagi.utils.dates import force_to_datetime


def xml_to_stock_report_helper(form, elem):
    tag = elem.tag
    tag = tag[tag.find('}') + 1:]  # strip out ns
    timestamp = force_to_datetime(
        elem.attrib.get('date') or form.received_on).replace(tzinfo=None)
    products = elem.findall('./{%s}entry' % stockconst.COMMTRACK_REPORT_XMLNS)
    transactions = [
        t for prod_entry in products for t in
        _xml_to_stock_transaction_helper(form.domain, timestamp, tag, elem,
                                         prod_entry)
    ]

    return StockReportHelper(form, timestamp, tag, transactions)


def _xml_to_stock_transaction_helper(domain, timestamp, action_tag,
                                     action_node, product_node):
    action_type = action_node.attrib.get('type')
    subaction = action_type
    product_id = product_node.attrib.get('id')

    def _txn(action, case_id, section_id, quantity):
        # warning: here be closures
        return StockTransactionHelper(
            domain=domain,
            timestamp=timestamp,
            product_id=product_id,
            quantity=Decimal(str(quantity)) if quantity is not None else None,
            action=action,
            case_id=case_id,
            section_id=section_id,
            subaction=subaction if subaction and subaction != action else None
            # note: no location id
        )

    def _yield_txns(section_id, quantity):
        # warning: here be closures
        if action_tag == 'balance':
            case_id = action_node.attrib['entity-id']
            yield _txn(
                action=(const.StockActions.STOCKONHAND if quantity > 0
                        else const.StockActions.STOCKOUT),
                case_id=case_id,
                section_id=section_id,
                quantity=quantity,
            )
        elif action_tag == 'transfer':
            src, dst = [action_node.attrib.get(k) for k in ('src', 'dest')]
            assert src or dst
            if src is not None:
                yield _txn(action=const.StockActions.CONSUMPTION, case_id=src,
                           section_id=section_id, quantity=quantity)
            if dst is not None:
                yield _txn(action=const.StockActions.RECEIPTS, case_id=dst,
                           section_id=section_id, quantity=quantity)

    def _quantity_or_none(value, section_id):
        try:
            return float(value)
        except (ValueError, TypeError):
            logging.error((
                "Non-numeric quantity submitted on domain %s for "
                "a %s ledger" % (domain, section_id)
            ))
            return None

    section_id = action_node.attrib.get('section-id', None)
    grouped_entries = section_id is not None
    if grouped_entries:
        quantity = _quantity_or_none(
            product_node.attrib.get('quantity'),
            section_id
        )
        # make sure quantity is not an empty, unset node value
        if quantity is not None:
            for txn in _yield_txns(section_id, quantity):
                yield txn
    else:
        values = [child for child in product_node]
        for value in values:
            section_id = value.attrib.get('section-id')
            quantity = _quantity_or_none(
                value.attrib.get('quantity'),
                section_id
            )
            # make sure quantity is not an empty, unset node value
            if quantity is not None:
                for txn in _yield_txns(section_id, quantity):
                    yield txn
