from decimal import Decimal
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from corehq.apps.commtrack.const import RequisitionActions
from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack import const
from corehq.apps.sms.api import send_sms_to_verified_number, MessageMetadata
from corehq import toggles
from lxml import etree
import logging

from corehq.form_processor.interfaces.supply import SupplyInterface
from dimagi.utils.couch.loosechange import map_reduce
from dimagi.utils.parsing import json_format_datetime
from datetime import datetime
from corehq.apps.commtrack.util import get_supply_point_and_location
from corehq.apps.commtrack.xmlutil import XML
from corehq.apps.products.models import Product
from corehq.apps.users.models import CouchUser
from corehq.apps.receiverwrapper import submit_form_locally
from xml.etree import ElementTree
from casexml.apps.case.mock import CaseBlock
from corehq.apps.commtrack.exceptions import (
    NoDefaultLocationException,
    NotAUserClassError)
import re
from corehq.form_processor.parsers.ledgers.helpers import StockTransactionHelper

logger = logging.getLogger('commtrack.sms')


class SMSError(RuntimeError):
    pass


def handle(verified_contact, text, msg=None):
    """top-level handler for incoming stock report messages"""
    domain = Domain.get_by_name(verified_contact.domain)
    if not domain.commtrack_enabled:
        return False

    try:
        if toggles.STOCK_AND_RECEIPT_SMS_HANDLER.enabled(domain):
            # handle special stock parser for custom domain logic
            data = StockAndReceiptParser(domain, verified_contact).parse(text.lower())
        else:
            # default report parser
            data = StockReportParser(domain, verified_contact).parse(text.lower())
        if not data:
            return False
    except NotAUserClassError:
        return False
    except Exception, e: # todo: should we only trap SMSErrors?
        if settings.UNIT_TESTING or settings.DEBUG:
            raise
        send_sms_to_verified_number(verified_contact, 'problem with stock report: %s' % str(e))
        return True

    process(domain.name, data)
    send_confirmation(verified_contact, data)
    return True


def process(domain, data):
    import pprint
    logger.debug(pprint.pformat(data))

    xml = to_instance(data)

    logger.debug(xml)

    submit_form_locally(
        instance=xml,
        domain=domain,
    )


class StockReportParser(object):
    """a helper object for parsing raw stock report texts"""

    def __init__(self, domain, v):
        self.domain = domain
        self.v = v

        self.location = None
        self.case = None
        u = v.owner

        if domain.commtrack_enabled:
            # if user is not actually a user, we let someone else process
            if not isinstance(u, CouchUser):
                raise NotAUserClassError

            # currently only support one location on the UI
            self.location = u.location
            if self.location:
                self.case = SupplyInterface(domain.name).get_by_location(self.location)

        self.C = domain.commtrack_settings

    def parse(self, text):
        """take in a text and return the parsed stock transactions"""
        args = text.split()

        if len(args) == 0:
            # we'll allow blank messages to propagate further in case some
            # other handler cares about them.
            return None

        action_keyword = args[0]
        args = args[1:]
        if not self.location:
            if len(args) == 0:
                # todo: this will change when users are tied to locations
                # though need to make sure that PACK and APPROVE still require location code
                # (since they refer to locations different from the sender's loc)
                raise SMSError("must specify a location code")
            self.case, self.location = self.get_supply_point_and_location(args[0])
            args = args[1:]

        action = self.C.action_by_keyword(action_keyword)
        if action and action.type == 'stock':
            # TODO: support single-action by product, as well as by action?
            self.verify_location_registration()
            self.case_id = self.case.case_id
            _tx = self.single_action_transactions(action, args)
        elif action and action.action in [
            RequisitionActions.REQUEST,
            RequisitionActions.FULFILL,
            RequisitionActions.RECEIPTS
        ]:
            # dropped support for this
            raise SMSError(_(
                "You can no longer use requisitions! Please contact your project supervisor for help"
            ))

        elif self.C.multiaction_enabled and action_keyword == self.C.multiaction_keyword:
            # multiple action stock report
            _tx = self.multiple_action_transactions(args)
        else:
            # initial keyword not recognized; delegate to another handler
            return None

        return self.unpack_transactions(_tx)

    def verify_location_registration(self):
        if not self.case:
            raise NoDefaultLocationException(
                _("You have not been registered with a default location yet."
                  "  Please register a default location for this user.")
            )

    def single_action_transactions(self, action, args):
        # special case to handle immediate stock-out reports
        if action.action == const.StockActions.STOCKOUT:
            if all(self.looks_like_prod_code(arg) for arg in args):
                for prod_code in args:
                    yield StockTransactionHelper(
                        domain=self.domain.name,
                        location_id=self.location.location_id,
                        case_id=self.case_id,
                        product_id=self.product_from_code(prod_code).get_id,
                        action=action.action,
                        subaction=action.subaction,
                        quantity=0,
                    )

                return
            else:
                raise SMSError("can't include a quantity for stock-out action")

        products = []
        for arg in args:
            if self.looks_like_prod_code(arg):
                products.append(self.product_from_code(arg))
            else:
                if not products:
                    raise SMSError('quantity "%s" doesn\'t have a product' % arg)
                if len(products) > 1:
                    raise SMSError('missing quantity for product "%s"' % products[-1].code)

                try:
                    value = int(arg)
                except:
                    raise SMSError('could not understand product quantity "%s"' % arg)

                for p in products:
                    yield StockTransactionHelper(
                        domain=self.domain.name,
                        location_id=self.location.location_id,
                        case_id=self.case_id,
                        product_id=p.get_id,
                        action=action.action,
                        subaction=action.subaction,
                        quantity=value,
                    )
                products = []
        if products:
            raise SMSError('missing quantity for product "%s"' % products[-1].code)

    def multiple_action_transactions(self, args):
        action = None

        # TODO: catch that we don't mix in requisiton and stock report keywords in the same multi-action message?

        _args = iter(args)

        def next():
            return _args.next()

        found_product_for_action = True
        while True:
            try:
                keyword = next()
            except StopIteration:
                if not found_product_for_action:
                    raise SMSError('product expected for action "%s"' % action)
                break

            old_action = action
            _next_action = self.C.action_by_keyword(keyword)
            if _next_action:
                action = _next_action
                if not found_product_for_action:
                    raise SMSError('product expected for action "%s"' % old_action.keyword)
                found_product_for_action = False
                continue

            try:
                product = self.product_from_code(keyword)
                found_product_for_action = True
            except:
                product = None
            if product:
                if not action:
                    raise SMSError('need to specify an action before product')
                elif action.action == const.StockActions.STOCKOUT:
                    value = 0
                else:
                    try:
                        value = int(next())
                    except (ValueError, StopIteration):
                        raise SMSError('quantity expected for product "%s"' % product.code)

                yield StockTransactionHelper(
                    domain=self.domain.name,
                    location_id=self.location.location_id,
                    case_id=self.case_id,
                    product_id=product.get_id,
                    action=action.action,
                    subaction=action.subaction,
                    quantity=value,
                )
                continue

            raise SMSError('do not recognize keyword "%s"' % keyword)

    def get_supply_point_and_location(self, loc_code):
        """return the supply point case referenced by loc_code"""
        case_location_tuple = get_supply_point_and_location(self.domain.name, loc_code)
        if not case_location_tuple:
            raise SMSError('invalid location code "%s"' % loc_code)
        return case_location_tuple

    def product_from_code(self, prod_code):
        """return the product doc referenced by prod_code"""
        prod_code = prod_code.lower()
        p = Product.get_by_code(self.domain.name, prod_code)
        if p is None:
            raise SMSError('invalid product code "%s"' % prod_code)
        return p

    def looks_like_prod_code(self, code):
        try:
            int(code)
            return False
        except ValueError:
            return True

    def unpack_transactions(self, txs):
        tx = list(txs)
        if not tx:
            raise SMSError("stock report doesn't have any transactions")

        return {
            'timestamp': datetime.utcnow(),
            'user': self.v.owner,
            'phone': self.v.phone_number,
            'location': self.location,
            'transactions': tx,
        }


class StockAndReceiptParser(StockReportParser):
    """
    This parser (originally written for EWS) allows
    a slightly different requirement for SMS formats,
    this class exists to break that functionality
    out of the default SMS handler to live in the ewsghana

    They send messages of the format:

        'nets 100.22'

    In this example, the data reflects:

        nets = product sms code
        100 = the facility stating that they have 100 nets
        20 = the facility stating that they received 20 in this period

    There is some duplication here, but it felt better to
    add duplication instead of complexity. The goal is to
    override only the couple methods that required modifications.
    """

    ALLOWED_KEYWORDS = ['join', 'help']

    def looks_like_prod_code(self, code):
        """
        Special for EWS, this version doesn't consider "10.20"
        as an invalid quantity.
        """
        try:
            float(code)
            return False
        except ValueError:
            return True

    def parse(self, text):
        args = text.split()

        if len(args) == 0:
            return None

        if args[0].lower() in self.ALLOWED_KEYWORDS:
            return None

        if not self.location:
            self.case, self.location = self.get_supply_point_and_location(args[0])
            args = args[1:]

        self.verify_location_registration()
        self.case_id = self.case.case_id
        action = self.C.action_by_keyword('soh')
        _tx = self.single_action_transactions(action, args)

        return self.unpack_transactions(_tx)

    def single_action_transactions(self, action, args):
        products = []
        for arg in args:
            if self.looks_like_prod_code(arg):
                products.append(self.product_from_code(arg))
            else:
                if not products:
                    raise SMSError('quantity "%s" doesn\'t have a product' % arg)
                if len(products) > 1:
                    raise SMSError('missing quantity for product "%s"' % products[-1].code)

                # NOTE also custom code here, must be formatted like 11.22
                if re.compile("^\d+\.\d+$").match(arg):
                    value = arg
                else:
                    raise SMSError('could not understand product quantity "%s"' % arg)

                for p in products:
                    # for EWS we have to do two transactions, one being a receipt
                    # and second being a transaction (that's reverse of the order
                    # the user provides them)
                    yield StockTransactionHelper(
                        domain=self.domain.name,
                        location_id=self.location.location_id,
                        case_id=self.case_id,
                        product_id=p.get_id,
                        action=const.StockActions.RECEIPTS,
                        quantity=Decimal(value.split('.')[1])
                    )
                    yield StockTransactionHelper(
                        domain=self.domain.name,
                        location_id=self.location.location_id,
                        case_id=self.case_id,
                        product_id=p.get_id,
                        action=const.StockActions.STOCKONHAND,
                        quantity=Decimal(value.split('.')[0])
                    )
                products = []
        if products:
            raise SMSError('missing quantity for product "%s"' % products[-1].code)


def verify_transaction_cases(transactions):
    """
    Make sure the transactions are all in a consistent state.
    Specifically, they all need to have the same case id.
    """
    assert transactions and all(
        tx.case_id == transactions[0].case_id for tx in transactions
    )


def process_transactions(E, transactions):
    balances = []
    transfers = []

    for tx in transactions:
        if tx.action in (
            const.StockActions.STOCKONHAND,
            const.StockActions.STOCKOUT,
            const.RequisitionActions.REQUEST
        ):
            balances.append(tx)
        elif tx.action == const.RequisitionActions.FULFILL:
            balances.append(tx)
            transfers.append(tx)
        else:
            transfers.append(tx)

    return process_balances(E, balances), process_transfers(E, transfers)


def process_balances(E, balances):
    if balances:
        if balances[0].action == const.RequisitionActions.REQUEST:
            section_id = 'ct-requested'
        elif balances[0].action == const.RequisitionActions.FULFILL:
            section_id = 'ct-fulfilled'
        else:
            section_id = 'stock'

        attr = {
            'section-id': section_id,
            'entity-id': balances[0].case_id
        }
        if balances[0].date:
            attr['date'] = balances[0].date

        return E.balance(
            attr,
            *[tx.to_xml() for tx in balances]
        )


def process_transfers(E, transfers):
    if transfers:
        attr = {
            'section-id': 'stock',
        }

        if transfers[0].action in [
            const.StockActions.RECEIPTS,
            const.RequisitionActions.FULFILL
        ]:
            here, there = ('dest', 'src')
        else:
            here, there = ('src', 'dest')

        attr[here] = transfers[0].case_id

        if transfers[0].subaction:
            attr['type'] = transfers[0].subaction

        return E.transfer(
            attr,
            *[tx.to_xml() for tx in transfers]
        )


def convert_transactions_to_blocks(E, transactions):
    """
    Converts a list of StockTransactions (which in xml are entity items)
    to lists inside of balance or transfer blocks, depending on their types
    """

    verify_transaction_cases(transactions)

    balances, transfers = process_transactions(E, transactions)

    stock_blocks = []
    if transfers:
        stock_blocks.append(transfers)
    if balances:
        stock_blocks.append(balances)

    return stock_blocks


def get_device_id(data):
    if data.get('phone'):
        return 'sms:%s' % data['phone']
    else:
        return None


def verify_transaction_actions(transactions):
    """
    Make sure the transactions are all in a consistent state.
    Specifically, they all need to have the same case id.
    """
    assert transactions and all(
        tx.action == transactions[0].action for tx in transactions
    )


def requisition_case_xml(data, stock_blocks):
    req_id = data['transactions'][0].case_id

    verify_transaction_actions(data['transactions'])
    action_type = data['transactions'][0].action
    if action_type == const.RequisitionActions.REQUEST:
        create = True
        close = False
        status = 'requested'
    elif action_type == const.RequisitionActions.FULFILL:
        create = False
        close = False
        status = 'fulfilled'
    elif action_type == const.RequisitionActions.RECEIPTS:
        create = False
        close = True
        status = 'received'
    else:
        raise NotImplementedError()

    req_case_block = ElementTree.tostring(CaseBlock(
        req_id,
        create=create,
        close=close,
        case_type=const.REQUISITION_CASE_TYPE,
        case_name='SMS Requisition',
        index={'parent_id': (
            const.SUPPLY_POINT_CASE_TYPE,
            data['location'].linked_supply_point()._id
        )},
        update={'requisition_status': status},
    ).as_xml())

    timestamp = data['transactions'][0].timestamp or datetime.utcnow()
    device_id = get_device_id(data)

    return """
        <data uiVersion="1" version="33" name="New Form" xmlns="%(xmlns)s">
            <meta>
                <deviceID>%(device_id)s</deviceID>
                <timeStart>%(timestamp)s</timeStart>
                <timeEnd>%(timestamp)s</timeEnd>
                <userID>%(user_id)s</userID>
            </meta>
            %(case_block)s
            %(stock_blocks)s
        </data>
    """ % {
        'case_block': req_case_block,
        'stock_blocks': '\n'.join(etree.tostring(b) for b in stock_blocks),
        'user_id': str(data['user']._id),
        'device_id': str(device_id) if device_id else '',
        'xmlns': const.SMS_XMLNS,
        'timestamp': json_format_datetime(timestamp)
    }


def to_instance(data):
    """convert the parsed sms stock report into an instance like what would be
    submitted from a commcare phone"""
    E = XML()
    M = XML(const.META_XMLNS, 'jrm')

    deviceID = get_device_id(data)
    timestamp = json_format_datetime(data['timestamp'])

    transactions = data['transactions']
    category = set(tx.category for tx in transactions).pop()
    stock_blocks = convert_transactions_to_blocks(E, transactions)

    if category == 'stock':
        root = E.stock_report(
            M.meta(
                M.userID(data['user']._id),
                M.deviceID(deviceID),
                M.timeStart(timestamp),
                M.timeEnd(timestamp)
            ),
            E.location(data['location']._id),
            *stock_blocks
        )
        return etree.tostring(root, encoding='utf-8', pretty_print=True)
    else:
        return requisition_case_xml(data, stock_blocks)


def truncate(text, maxlen, ellipsis='...'):
    if len(text) > maxlen:
        return text[:maxlen-len(ellipsis)] + ellipsis
    else:
        return text


def send_confirmation(v, data):
    C = CommtrackConfig.for_domain(v.domain)

    static_loc = data['location']
    location_name = static_loc.name
    metadata = MessageMetadata(location_id=static_loc.get_id)
    tx_by_action = map_reduce(lambda tx: [(tx.action_config(C).name,)], data=data['transactions'], include_docs=True)

    def summarize_action(action, txs):
        return '%s %s' % (txs[0].action_config(C).keyword.upper(), ' '.join(sorted(tx.fragment() for tx in txs)))

    msg = 'received stock report for %s(%s) %s' % (
        static_loc.site_code,
        truncate(location_name, 20),
        ' '.join(sorted(summarize_action(a, txs) for a, txs in tx_by_action.iteritems()))
    )

    send_sms_to_verified_number(v, msg, metadata=metadata)
