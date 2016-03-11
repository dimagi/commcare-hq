from corehq.apps.commtrack.processing import compute_ledger_values
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.interfaces.ledger_processor import LedgerProcessorInterface, StockModelUpdateResult, \
    LedgerDBInterface
from corehq.form_processor.models import LedgerValue, LedgerTransaction


class LedgerDBSQL(LedgerDBInterface):
    def get_ledgers_for_case(self, case_id):
        return LedgerAccessorSQL.get_ledger_values_for_case(case_id)

    def _get_ledger(self, unique_ledger_reference):
        try:
            return LedgerAccessorSQL.get_ledger_value(**unique_ledger_reference._asdict())
        except LedgerValue.DoesNotExist:
            return None

    def get_current_ledger_value(self, unique_ledger_reference):
        ledger = self.get_ledger(unique_ledger_reference)
        return ledger.balance if ledger else 0


class LedgerProcessorSQL(LedgerProcessorInterface):
    """
    Ledger processor for new SQL-based code.
    """

    def get_models_to_update(self, stock_report_helper, ledger_db=None):
        ledger_db = ledger_db or LedgerDBSQL()
        latest_values = {}
        to_save = []
        for stock_trans in stock_report_helper.transactions:
            def _lazy_original_balance():
                # needs to be in closures because it's zero-argument.
                # see compute_ledger_values for more information
                reference = stock_trans.ledger_reference
                if reference not in latest_values:
                    latest_values[reference] = ledger_db.get_current_ledger_value(reference)
                return latest_values[reference]

            new_ledger_values = compute_ledger_values(
                _lazy_original_balance, stock_report_helper.report_type, stock_trans.relative_quantity
            )

            ledger_value = ledger_db.get_ledger(stock_trans.ledger_reference)
            if not ledger_value:
                ledger_value = LedgerValue(**stock_trans.ledger_reference._asdict())

            ledger_value.track_create(
                _get_ledget_transaction(_lazy_original_balance, stock_report_helper, stock_trans, new_ledger_values.balance)
            )

            # only do this after we've created the transaction otherwise we'll get the wrong delta
            ledger_value.balance = new_ledger_values.balance
            latest_values[stock_trans.ledger_reference] = new_ledger_values.balance
            to_save.append(ledger_value)

        return StockModelUpdateResult(to_save=to_save)


def _get_ledget_transaction(lazy_original_balance, stock_report_helper, stock_trans, new_balance):
    return LedgerTransaction(
        form_id=stock_report_helper.form_id,
        server_date=stock_report_helper.server_date,
        report_date=stock_report_helper.timestamp,
        type=_report_type_to_ledger_type(stock_report_helper.report_type),
        case_id=stock_trans.case_id,
        section_id=stock_trans.section_id,
        entry_id=stock_trans.product_id,
        user_defined_type=stock_trans.subaction,
        delta=new_balance - lazy_original_balance(),
        updated_balance=new_balance
    )


def _report_type_to_ledger_type(report_type):
    from casexml.apps.stock.const import REPORT_TYPE_BALANCE, REPORT_TYPE_TRANSFER
    if report_type == REPORT_TYPE_BALANCE:
        return LedgerTransaction.TYPE_BALANCE
    if report_type == REPORT_TYPE_TRANSFER:
        return LedgerTransaction.TYPE_TRANSFER

    raise ValueError('Invalid stock report type {}!'.format(report_type))
