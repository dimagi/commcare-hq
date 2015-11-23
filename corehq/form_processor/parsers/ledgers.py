from collections import namedtuple
from dimagi.ext import jsonobject
from dimagi.utils import parsing as dateparse
from django.utils.translation import ugettext as _
from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.models import CommCareCaseAction
from casexml.apps.case.xform import is_device_report
from casexml.apps.case.xml.parser import AbstractAction
from corehq.apps.commtrack import const
from corehq.apps.commtrack.const import StockActions
from corehq.apps.commtrack.exceptions import MissingProductId
from corehq.apps.commtrack.models import CommtrackActionConfig
from corehq.apps.commtrack.xmlutil import XML
from corehq.apps.products.models import Product


CaseActionIntent = namedtuple('CaseActionIntent', ['case_id', 'form_id', 'is_deprecation', 'action'])
StockFormActions = namedtuple('StockFormActions', ['stock_report_helpers', 'case_action_intents'])


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
