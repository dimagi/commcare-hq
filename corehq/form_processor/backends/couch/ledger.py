from casexml.apps.stock import const
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.processing import compute_ledger_values
from corehq.form_processor.interfaces.ledger_processor import LedgerProcessorInterface, StockModelUpdateResult, \
    LedgerDB
from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference


class LedgerProcessorCouch(LedgerProcessorInterface):
    """
    Ledger processor for existing/legacy code.

    Note that this class still stores ledgers in SQL, but it relies on the couch-based
    form and case models, which is why it lives in the "couch" module.
    """

    def get_models_to_update(self, stock_report_helper, ledger_db=None):
        ledger_db = ledger_db or LedgerDB(self)
        assert stock_report_helper.domain == self.domain
        if stock_report_helper.deprecated:
            return StockModelUpdateResult(
                to_delete=StockReport.objects.filter(domain=self.domain, form_id=stock_report_helper.form_id)
            )
        if stock_report_helper.report_type not in const.VALID_REPORT_TYPES:
            return None
        report_model = _get_model_for_stock_report(self.domain, stock_report_helper)
        to_save = [report_model]
        for transaction_helper in stock_report_helper.transactions:
            to_save.append(_get_model_for_stock_transaction(report_model, transaction_helper, ledger_db))
        return StockModelUpdateResult(to_save=to_save)

    def get_ledgers_for_case(self, case_id):
        from corehq.apps.commtrack.models import StockState
        return StockState.objects.filter(case_id=case_id)

    def get_current_ledger_value(self, unique_ledger_reference):
        latest_txn = StockTransaction.latest(
            case_id=unique_ledger_reference.case_id,
            section_id=unique_ledger_reference.section_id,
            product_id=unique_ledger_reference.entry_id,
        )
        return latest_txn.stock_on_hand if latest_txn else 0


def _get_model_for_stock_report(domain, stock_report_helper):
    return StockReport(
        form_id=stock_report_helper.form_id,
        date=stock_report_helper.timestamp,
        type=stock_report_helper.report_type,
        domain=domain,
        server_date=stock_report_helper.server_date,
    )


def _get_model_for_stock_transaction(report, transaction_helper, ledger_db):
    assert report.type in const.VALID_REPORT_TYPES
    txn = StockTransaction(
        report=report,
        case_id=transaction_helper.case_id,
        section_id=transaction_helper.section_id,
        product_id=transaction_helper.product_id,
        type=transaction_helper.action,
        subtype=transaction_helper.subaction,
    )

    def lazy_original_balance():
        return ledger_db.get_current_balance(_stock_transaction_to_unique_ledger_reference(txn))

    new_ledger_values = compute_ledger_values(
        lazy_original_balance, report.type,
        transaction_helper.relative_quantity)

    txn.stock_on_hand = new_ledger_values.balance
    txn.quantity = new_ledger_values.delta

    if report.domain:
        # set this as a shortcut for post save signal receivers
        txn.domain = report.domain

    # update the ledger DB in case later transactions reference the same ledger item
    ledger_db.set_current_balance(_stock_transaction_to_unique_ledger_reference(txn), txn.stock_on_hand)
    return txn


def _stock_transaction_to_unique_ledger_reference(txn):
    return UniqueLedgerReference(case_id=txn.case_id, section_id=txn.section_id, entry_id=txn.product_id)
