from casexml.apps.stock import const
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.processing import compute_ledger_values, rebuild_stock_state
from corehq.form_processor.interfaces.ledger_processor import LedgerProcessorInterface, StockModelUpdateResult, \
    LedgerDBInterface
from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference


class LedgerDBCouch(LedgerDBInterface):
    def get_ledgers_for_case(self, case_id):
        from corehq.apps.commtrack.models import StockState
        return StockState.objects.filter(case_id=case_id)

    def _get_ledger(self, unique_ledger_reference):
        from corehq.apps.commtrack.models import StockState
        try:
            return StockState.objects.get(
                case_id=unique_ledger_reference.case_id,
                section_id=unique_ledger_reference.section_id,
                product_id=unique_ledger_reference.entry_id,
            )
        except StockState.DoesNotExist:
            return None

    def get_current_ledger_value(self, unique_ledger_reference):
        latest_txn = StockTransaction.latest(
            case_id=unique_ledger_reference.case_id,
            section_id=unique_ledger_reference.section_id,
            product_id=unique_ledger_reference.entry_id,
        )
        return latest_txn.stock_on_hand if latest_txn else 0


class LedgerProcessorCouch(LedgerProcessorInterface):
    """
    Ledger processor for existing/legacy code.

    Note that this class still stores ledgers in SQL, but it relies on the couch-based
    form and case models, which is why it lives in the "couch" module.
    """

    def get_models_to_update(self, form_id, stock_report_helpers, deprecated_helpers, ledger_db=None):
        ledger_db = ledger_db or LedgerDBCouch()
        result = StockModelUpdateResult()

        if len(deprecated_helpers):
            form_ids = list({deprecated_helper.form_id for deprecated_helper in deprecated_helpers})
            assert form_ids == [form_id]
            result.to_delete.append(StockReport.objects.filter(domain=self.domain, form_id=form_id))

        for helper in stock_report_helpers:
            if helper.report_type not in const.VALID_REPORT_TYPES:
                continue

            report_model = _get_model_for_stock_report(self.domain, helper)
            result.to_save.append(report_model)
            for transaction_helper in helper.transactions:
                transaction = _get_model_for_stock_transaction(
                    report_model, transaction_helper, ledger_db
                )
                result.to_save.append(transaction)

        return result

    def rebuild_ledger_state(self, case_id, section_id, entry_id):
        rebuild_stock_state(case_id, section_id, entry_id)

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
