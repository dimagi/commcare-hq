from collections import namedtuple
from dimagi.ext import jsonobject
from dimagi.utils import parsing as dateparse
from django.utils.translation import ugettext as _
from corehq.apps.commtrack import const
from corehq.apps.commtrack.const import StockActions
from corehq.apps.commtrack.exceptions import MissingProductId
from corehq.apps.commtrack.models import CommtrackActionConfig
from corehq.apps.commtrack.xmlutil import XML
from corehq.apps.products.models import Product


UniqueLedgerReference = namedtuple('UniqueLedgerReference', ['case_id', 'section_id', 'entry_id'])


class StockReportHelper(jsonobject.JsonObject):
    """
    Intermediate class for dealing with stock XML
    """

    domain = jsonobject.StringProperty()
    form_id = jsonobject.StringProperty()
    timestamp = jsonobject.DateTimeProperty()
    tag = jsonobject.StringProperty()
    transactions = jsonobject.ListProperty(lambda: StockTransactionHelper)
    server_date = jsonobject.DateTimeProperty()
    deprecated = jsonobject.BooleanProperty()

    @property
    def report_type(self):
        # this is for callers to be able to use a less confusing name
        return self.tag

    @classmethod
    def make_from_form(cls, form, timestamp, tag, transactions):
        deprecated = form.is_deprecated
        return cls(
            domain=form.domain,
            form_id=form.form_id if not deprecated else form.orig_id,
            timestamp=timestamp,
            tag=tag,
            transactions=transactions,
            server_date=form.received_on,
            deprecated=deprecated,
        )

    def validate(self):
        """
        Validates this object as best we can and raises Exceptions if we find anything invalid .
        """
        if any(transaction_helper.product_id in ('', None) for transaction_helper in self.transactions):
            raise MissingProductId(_('Product IDs must be set for all ledger updates!'))


class StockTransactionHelper(jsonobject.JsonObject):
    """
    Helper class for transactions
    """

    product_id = jsonobject.StringProperty()
    action = jsonobject.StringProperty()
    subaction = jsonobject.StringProperty()
    domain = jsonobject.StringProperty()
    quantity = jsonobject.DecimalProperty()
    location_id = jsonobject.StringProperty()
    timestamp = jsonobject.DateTimeProperty()
    case_id = jsonobject.StringProperty()
    section_id = jsonobject.StringProperty()

    @property
    def ledger_reference(self):
        return UniqueLedgerReference(
            case_id=self.case_id, section_id=self.section_id, entry_id=self.product_id
        )

    @property
    def relative_quantity(self):
        """
        Gets the quantity of this transaction as a positive or negative number
        depending on the action/context
        """
        if self.action == const.StockActions.CONSUMPTION:
            return -self.quantity
        else:
            return self.quantity

    def action_config(self, commtrack_config):
        action = CommtrackActionConfig(action=self.action,
                                       subaction=self.subaction)
        for a in commtrack_config.all_actions:
            if a.name == action.name:
                return a
        return None

    @property
    def date(self):
        if self.timestamp:
            return dateparse.json_format_datetime(self.timestamp)

    def to_xml(self, E=None, **kwargs):
        if not E:
            E = XML()

        return E.entry(
            id=self.product_id,
            quantity=str(self.quantity if self.action != StockActions.STOCKOUT
                         else 0),
        )

    @property
    def category(self):
        return 'stock'

    def fragment(self):
        """
        A short string representation of this to be used in sms correspondence
        """
        if self.quantity is not None:
            quant = self.quantity
        else:
            quant = ''
        # FIXME product fetch here is inefficient
        return '%s%s' % (Product.get(self.product_id).code.lower(), quant)

    def __repr__(self):
        return '{action} ({subaction}): {quantity} (loc: {location_id}, product: {product_id})'.format(
            action=self.action,
            subaction=self.subaction,
            quantity=self.quantity,
            location_id=self.location_id,
            product_id=self.product_id,
        )
