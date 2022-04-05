import logging
from collections import namedtuple
from itertools import groupby

from django.utils.translation import gettext as _

from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.stock import const as stockconst
from dimagi.utils.decorators.log_exception import log_exception

from corehq.form_processor.casedb_base import AbstractCaseDbCache
from corehq.form_processor.exceptions import MissingFormXml
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.parsers.ledgers import get_stock_actions, get_ledger_case_action_intents
from corehq.util.metrics.load_counters import ledger_load_counter

logger = logging.getLogger('commtrack.incoming')

COMMTRACK_LEGACY_REPORT_XMLNS = 'http://commtrack.org/legacy/stock_report'


class StockProcessingResult(object):
    """
    An object used to collect the changes that are made during stock
    processing so that they can be made more atomic
    """

    def __init__(self, xform, relevant_cases=None, stock_report_helpers=None):
        self.domain = xform.domain
        self.xform = xform
        self.relevant_cases = relevant_cases or []
        self.stock_report_helpers = stock_report_helpers or []
        self.models_to_save = None
        self.models_to_delete = None
        self.populated = False
        self.cases_with_deprecated_transactions = None

    def populate_models(self):
        self.populated = True

        interface = FormProcessorInterface(domain=self.domain)
        processor = interface.ledger_processor
        ledger_db = interface.ledger_db

        track_load = ledger_load_counter("process_stock", self.domain)
        normal_helpers = []
        deprecated_helpers = []
        for helper in self.stock_report_helpers:
            assert helper.domain == self.domain
            if not helper.deprecated:
                normal_helpers.append(helper)
            else:
                deprecated_helpers.append(helper)
            track_load(len(helper.transactions))

        models_result = processor.get_models_to_update(
            self.xform.form_id, normal_helpers, deprecated_helpers, ledger_db
        )
        self.models_to_save, self.models_to_delete = models_result

        self.cases_with_deprecated_transactions = {
            trans.case_id for srh in deprecated_helpers for trans in srh.transactions
        }

    def commit(self):
        assert self.populated
        for to_delete in self.models_to_delete:
            to_delete.delete()
        for to_save in self.models_to_save:
            to_save.save()

    def finalize(self):
        """
        Finalize anything else that needs to happen - this runs after models are saved.
        """
        pass


LedgerValues = namedtuple('LedgerValues', ['balance', 'delta'])


def compute_ledger_values(lazy_original_balance, report_type, quantity):
    """
    lazy_original_balance:
        a zero-argument function returning original balance
        the original_balance is only used in the case of a transfer
        and it may be computationally expensive for the caller to provide
        putting it behind a function lets compute_ledger_values decide
        whether it's necessary to do that work
    report_type:
        REPORT_TYPE_BALANCE or REPORT_TYPE_TRANSFER
    quantity:
        the associated quantity, interpreted as a delta for transfers
        and a total balance for balances

    """
    if report_type == stockconst.REPORT_TYPE_BALANCE:
        new_balance = quantity
        # this is currently always 0 because of inferred transactions
        new_delta = 0
    elif report_type == stockconst.REPORT_TYPE_TRANSFER:
        original_balance = lazy_original_balance()
        new_delta = quantity
        new_balance = new_delta + (original_balance if original_balance else 0)
    else:
        raise ValueError()
    return LedgerValues(new_balance, new_delta)


@log_exception()
def process_stock(xforms, case_db=None):
    """
    process the commtrack xml constructs in an incoming submission
    """
    if not case_db:
        case_db = FormProcessorInterface(xforms[0].domain).casedb_cache(
            domain=xforms[0].domain,
            load_src="process_stock",
        )
    else:
        assert isinstance(case_db, AbstractCaseDbCache)

    stock_report_helpers = []
    case_action_intents = []
    sorted_forms = sorted(xforms, key=lambda f: 1 if f.is_deprecated else 0)
    for xform in sorted_forms:
        try:
            actions_for_form = get_stock_actions(xform)
            stock_report_helpers += actions_for_form.stock_report_helpers
            case_action_intents += actions_for_form.case_action_intents
        except MissingFormXml:
            if not xform.is_deprecated:
                raise

            # in the case where the XML is missing for the deprecated form add a
            # deprecation intent for all cases touched by the primary form
            case_ids = {intent.case_id for intent in case_action_intents}
            case_action_intents += get_ledger_case_action_intents(xform, case_ids)

    # validate the parsed transactions
    for stock_report_helper in stock_report_helpers:
        stock_report_helper.validate()

    relevant_cases = mark_cases_changed(case_action_intents, case_db)
    return StockProcessingResult(
        xform=sorted_forms[0],
        relevant_cases=relevant_cases,
        stock_report_helpers=stock_report_helpers,
    )


def mark_cases_changed(case_action_intents, case_db):
    relevant_cases = []
    # touch every case for proper ota restore logic syncing to be preserved
    for case_id, intents in groupby(case_action_intents, lambda intent: intent.case_id):
        case = case_db.get(case_id)
        relevant_cases.append(case)
        if case is None:
            raise IllegalCaseId(
                _('Ledger transaction references invalid Case ID "{}"')
                .format(case_id))

        deprecation_intent = None
        intents = list(intents)
        if len(intents) > 1:
            primary_intent, deprecation_intent = sorted(case_action_intents, key=lambda i: i.is_deprecation)
        else:
            [intent] = intents
            if intent.is_deprecation:
                primary_intent = None
                deprecation_intent = intent
            else:
                primary_intent = intent
        case_db.apply_action_intents(case, primary_intent, deprecation_intent)
        case_db.mark_changed(case)

    return relevant_cases
