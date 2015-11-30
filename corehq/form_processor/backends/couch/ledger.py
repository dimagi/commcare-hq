from corehq.form_processor.interfaces.ledger_processor import LedgerProcessorInterface


class LedgerProcessorCouch(LedgerProcessorInterface):
    """
    Ledger processor for existing/legacy code.

    Note that this class still stores ledgers in SQL, but it relies on the couch-based
    form and case models, which is why it lives in the "couch" module.
    """

    def create_models_for_stock_report_helper(self, stock_report_helper):
        from corehq.apps.commtrack.processing import create_models_for_stock_report
        return create_models_for_stock_report(self.domain, stock_report_helper)

    def delete_models_for_stock_report_helper(self, stock_report_helper):
        from corehq.apps.commtrack.processing import delete_models_for_stock_report
        return delete_models_for_stock_report(self.domain, stock_report_helper)

    def get_ledgers_for_case(self, case_id):
        from corehq.apps.commtrack.models import StockState
        return StockState.objects.filter(case_id=case_id)
