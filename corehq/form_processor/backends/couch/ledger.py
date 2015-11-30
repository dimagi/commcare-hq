from django.db import transaction
from casexml.apps.stock import const
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.processing import compute_ledger_values
from corehq.form_processor.interfaces.ledger_processor import LedgerProcessorInterface


class LedgerProcessorCouch(LedgerProcessorInterface):
    """
    Ledger processor for existing/legacy code.

    Note that this class still stores ledgers in SQL, but it relies on the couch-based
    form and case models, which is why it lives in the "couch" module.
    """

    @transaction.atomic
    def create_models_for_stock_report_helper(self, stock_report_helper):
        """
        Save stock report and stock transaction models to the database.
        """
        assert stock_report_helper.domain == self.domain
        if stock_report_helper.tag not in const.VALID_REPORT_TYPES:
            return
        report = _create_model_for_stock_report(self.domain, stock_report_helper)
        for transaction_helper in stock_report_helper.transactions:
            _create_model_for_stock_transaction(report, transaction_helper)

    @transaction.atomic
    def delete_models_for_stock_report_helper(self, stock_report_helper):
        """
        Delete all stock reports and stock transaction models associated with the helper from the database.
        """
        assert stock_report_helper.domain == self.domain
        StockReport.objects.filter(domain=self.domain, form_id=stock_report_helper.form_id).delete()

    def get_ledgers_for_case(self, case_id):
        from corehq.apps.commtrack.models import StockState
        return StockState.objects.filter(case_id=case_id)


def _create_model_for_stock_report(domain, stock_report_helper):
    return StockReport.objects.create(
        form_id=stock_report_helper.form_id,
        date=stock_report_helper.timestamp,
        type=stock_report_helper.report_type,
        domain=domain,
        server_date=stock_report_helper.server_date,
    )


def _create_model_for_stock_transaction(report, transaction_helper):
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
        previous_transaction = txn.get_previous_transaction()
        if previous_transaction:
            return previous_transaction.stock_on_hand
        else:
            return None

    new_ledger_values = compute_ledger_values(
        lazy_original_balance, report.type,
        transaction_helper.relative_quantity)

    txn.stock_on_hand = new_ledger_values.balance
    txn.quantity = new_ledger_values.delta

    if report.domain:
        # set this as a shortcut for post save signal receivers
        txn.domain = report.domain
    txn.save()
    return txn
