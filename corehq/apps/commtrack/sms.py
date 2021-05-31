import logging
import re
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from lxml import etree

from dimagi.utils.couch.loosechange import map_reduce
from dimagi.utils.parsing import json_format_datetime

from corehq import toggles
from corehq.apps.commtrack import const
from corehq.apps.commtrack.exceptions import (
    NoDefaultLocationException,
    NotAUserClassError,
    RequisitionsHaveBeenRemoved,
)
from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.commtrack.util import get_supply_point_and_location
from corehq.apps.commtrack.xmlutil import XML
from corehq.apps.domain.models import Domain
from corehq.apps.products.models import SQLProduct
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.sms.api import MessageMetadata, send_sms_to_verified_number
from corehq.apps.users.models import CouchUser
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.form_processor.parsers.ledgers.helpers import (
    StockTransactionHelper,
)

logger = logging.getLogger('commtrack.sms')


class SMSError(RuntimeError):
    pass


def handle(verified_contact, text, msg):
    """top-level handler for incoming stock report messages"""
    domain_obj = Domain.get_by_name(verified_contact.domain)
    if not domain_obj.commtrack_enabled:
        return False

    try:
        data = StockReportParser(domain_obj, verified_contact).parse(text.lower())
        if not data:
            return False
    except NotAUserClassError:
        return False
    except Exception as e:
        if settings.UNIT_TESTING or settings.DEBUG:
            raise
        send_sms_to_verified_number(verified_contact, 'problem with stock report: %s' % str(e))
        return True

    process(domain_obj.name, data)
    send_confirmation(verified_contact, data)
    return True


def process(domain, data):
    xml = to_instance(data)

    logger.debug(xml)

    submit_form_locally(
        instance=xml,
        domain=domain,
    )


class StockReportParser(object):
    """a helper object for parsing raw stock report texts"""

    def __init__(self, domain, verified_contact, location=None):
        self.domain = domain
        self.verified_contact = verified_contact

        self.location = location
        self.case = None
        u = verified_contact.owner

        if domain.commtrack_enabled:
            # if user is not actually a user, we let someone else process
            if not isinstance(u, CouchUser):
                raise NotAUserClassError

            if not self.location:
                self.location = u.location

            if self.location:
                self.case = SupplyInterface(domain.name).get_by_location(self.location)

        self.commtrack_settings = domain.commtrack_settings

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

        action = self.commtrack_settings.action_by_keyword(action_keyword)
        if action:
            # TODO: support single-action by product, as well as by action?
            self.verify_location_registration()
            self.case_id = self.case.case_id
            _tx = self.single_action_transactions(action, args)
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
                        product_id=self.product_from_code(prod_code).product_id,
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

                for product in products:
                    yield StockTransactionHelper(
                        domain=self.domain.name,
                        location_id=self.location.location_id,
                        case_id=self.case_id,
                        product_id=product.product_id,
                        action=action.action,
                        subaction=action.subaction,
                        quantity=value,
                    )
                products = []
        if products:
            raise SMSError('missing quantity for product "%s"' % products[-1].code)

    def get_supply_point_and_location(self, loc_code):
        """return the supply point case referenced by loc_code"""
        case_location_tuple = get_supply_point_and_location(self.domain.name, loc_code)
        if not case_location_tuple:
            raise SMSError('invalid location code "%s"' % loc_code)
        return case_location_tuple

    def product_from_code(self, prod_code):
        """return the product doc referenced by prod_code"""
        prod_code = prod_code.lower()
        try:
            return SQLProduct.objects.get(domain=self.domain.name, code__iexact=prod_code)
        except SQLProduct.DoesNotExist:
            raise SMSError('invalid product code "%s"' % prod_code)

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
            'user': self.verified_contact.owner,
            'phone': self.verified_contact.phone_number,
            'location': self.location,
            'transactions': tx,
        }


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
        ):
            balances.append(tx)
        else:
            transfers.append(tx)

    return process_balances(E, balances), process_transfers(E, transfers)


def process_balances(E, balances):
    if balances:
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
        raise RequisitionsHaveBeenRemoved()


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
        ' '.join(sorted(summarize_action(a, txs) for a, txs in tx_by_action.items()))
    )

    send_sms_to_verified_number(v, msg, metadata=metadata)
