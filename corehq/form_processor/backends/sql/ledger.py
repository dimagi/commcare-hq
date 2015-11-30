from django.db import transaction
from corehq.apps.commtrack.processing import compute_ledger_values
from corehq.form_processor.interfaces.ledger_processor import LedgerProcessorInterface
from corehq.form_processor.models import LedgerValue


class LedgerProcessorSQL(LedgerProcessorInterface):
    """
    Ledger processor for new SQL-based code.
    """

    @transaction.atomic
    def create_models_for_stock_report_helper(self, stock_report_helper):
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
        for touched_ledger_reference, quantity in latest_values.items():
            ledger_value, created = LedgerValue.objects.get_or_create(
                defaults={'balance': quantity},
                **touched_ledger_reference._asdict()
            )
            if not created and ledger_value.quantity != quantity:
                ledger_value.balance = quantity
                ledger_value.save()

    def delete_models_for_stock_report_helper(self, stock_report_helper):
        pass

    def get_ledgers_for_case(self, case_id):
        return LedgerValue.objects.filter(case_id=case_id)

    def get_current_ledger_value(self, unique_ledger_reference):
        # todo
        return 0
