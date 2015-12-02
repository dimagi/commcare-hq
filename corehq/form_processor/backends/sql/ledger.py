from corehq.apps.commtrack.processing import compute_ledger_values
from corehq.form_processor.interfaces.ledger_processor import LedgerProcessorInterface, StockModelUpdateResult
from corehq.form_processor.models import LedgerValue


class LedgerProcessorSQL(LedgerProcessorInterface):
    """
    Ledger processor for new SQL-based code.
    """

    def get_models_to_update(self, stock_report_helper, ledger_db=None):
        latest_values = {}
        for stock_trans in stock_report_helper.transactions:
            def _lazy_original_balance():
                # needs to be in closures because it's zero-argument.
                # see compute_ledger_values for more information
                if stock_trans.ledger_reference in latest_values:
                    return latest_values[stock_trans.ledger_reference]
                else:
                    return self.get_current_ledger_value(stock_trans.ledger_reference)

            new_ledger_values = compute_ledger_values(
                _lazy_original_balance, stock_report_helper.report_type, stock_trans.relative_quantity
            )
            latest_values[stock_trans.ledger_reference] = new_ledger_values.balance

        to_save = []
        for touched_ledger_reference, quantity in latest_values.items():
            try:
                ledger_value = LedgerValue.objects.get(
                    **touched_ledger_reference._asdict()
                )
            except LedgerValue.DoesNotExist:
                ledger_value = LedgerValue(**touched_ledger_reference._asdict())
            ledger_value.balance = quantity
            to_save.append(ledger_value)
        return StockModelUpdateResult(to_save=to_save)

    def get_ledgers_for_case(self, case_id):
        return LedgerValue.objects.filter(case_id=case_id)

    def get_current_ledger_value(self, unique_ledger_reference):
        try:
            return LedgerValue.objects.get(**unique_ledger_reference._asdict()).balance
        except LedgerValue.DoesNotExist:
            return 0
