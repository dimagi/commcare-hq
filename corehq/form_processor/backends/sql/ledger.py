from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.commtrack.processing import compute_ledger_values
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.exceptions import LedgerValueNotFound
from corehq.form_processor.interfaces.ledger_processor import LedgerProcessorInterface, StockModelUpdateResult, \
    LedgerDBInterface
from corehq.form_processor.models import LedgerValue, LedgerTransaction
from corehq.util.datadog.utils import ledger_load_counter


class LedgerDBSQL(LedgerDBInterface):

    def get_ledgers_for_case(self, case_id):
        return LedgerAccessorSQL.get_ledger_values_for_case(case_id)

    def _get_ledger(self, unique_ledger_reference):
        try:
            return LedgerAccessorSQL.get_ledger_value(**unique_ledger_reference._asdict())
        except LedgerValueNotFound:
            return None


class LedgerProcessorSQL(LedgerProcessorInterface):
    """
    Ledger processor for new SQL-based code.
    """

    def get_models_to_update(self, form_id, stock_report_helpers, deprecated_helpers, ledger_db=None):
        ledger_db = ledger_db or LedgerDBSQL()
        result = StockModelUpdateResult()

        ledgers_needing_rebuild = {
            deprecated_transaction.ledger_reference
            for deprecated_helper in deprecated_helpers
            for deprecated_transaction in deprecated_helper.transactions
        }

        updated_ledgers = {}
        for helper in stock_report_helpers:
            for stock_trans in helper.transactions:
                ledger_value = self._process_transaction(helper, stock_trans, ledger_db)
                updated_ledgers[ledger_value.ledger_reference] = ledger_value

        for ledger_reference, ledger_value in updated_ledgers.items():
            if ledger_reference in ledgers_needing_rebuild:
                ledgers_needing_rebuild.remove(ledger_reference)
                rebuilt_ledger_value = self._rebuild_ledger(form_id, ledger_value)
                result.to_save.append(rebuilt_ledger_value)
            else:
                result.to_save.append(ledger_value)

        # rebuild any ledgers that are no longer updated by this form
        for reference in ledgers_needing_rebuild:
            ledger_value = ledger_db.get_ledger(reference)
            rebuilt_ledger_value = self._rebuild_ledger(form_id, ledger_value)
            result.to_save.append(rebuilt_ledger_value)

        return result

    @staticmethod
    def _process_transaction(stock_report_helper, stock_trans, ledger_db):
        def _lazy_original_balance():
            # needs to be in closures because it's zero-argument.
            # see compute_ledger_values for more information
            reference = stock_trans.ledger_reference
            return ledger_db.get_current_ledger_value(reference)

        new_ledger_values = compute_ledger_values(
            _lazy_original_balance, stock_report_helper.report_type, stock_trans.relative_quantity
        )
        ledger_value = ledger_db.get_ledger(stock_trans.ledger_reference)
        if not ledger_value:
            ledger_value = LedgerValue(**stock_trans.ledger_reference._asdict())
            ledger_value.domain = stock_report_helper.domain
            ledger_db.set_ledger(ledger_value)
        transaction = _get_ledger_transaction(
            _lazy_original_balance,
            stock_report_helper,
            stock_trans,
            new_ledger_values.balance
        )
        ledger_value.track_create(transaction)
        # only do this after we've created the transaction otherwise we'll get the wrong delta
        ledger_value.balance = new_ledger_values.balance
        ledger_value.last_modified = stock_report_helper.server_date  # form.received_on
        ledger_value.last_modified_form_id = stock_report_helper.form_id
        return ledger_value

    def _rebuild_ledger(self, form_id, ledger_value):
        """
        Rebuild a LedgerValue and its associated transactions during a form edit workflow.

        :param form_id: ID of edited form
        :param ledger_value: LedgerValue to rebuild with transactions from new form tracked on the model
        :return: updated LedgerValue object
        """
        transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(
            **ledger_value.ledger_reference._asdict()
        )
        transaction_excluding_deprecated_form = [tx for tx in transactions if tx.form_id != form_id]
        new_transactions = ledger_value.get_tracked_models_to_create(LedgerTransaction)
        all_transactions = transaction_excluding_deprecated_form + new_transactions
        sorted_transactions = sorted(all_transactions, key=lambda t: t.report_date)

        ledger_value.clear_tracked_models(LedgerTransaction)
        ledger_value = self._rebuild_ledger_value_from_transactions(
            ledger_value, sorted_transactions, self.domain)
        return ledger_value

    def rebuild_ledger_state(self, case_id, section_id, entry_id):
        LedgerProcessorSQL.hard_rebuild_ledgers(self.domain, case_id, section_id, entry_id)

    @staticmethod
    def hard_rebuild_ledgers(domain, case_id, section_id, entry_id):
        transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(case_id, section_id, entry_id)
        if not transactions:
            LedgerAccessorSQL.delete_ledger_values(case_id, section_id, entry_id)
            return
        ledger_value = LedgerAccessorSQL.get_ledger_value(case_id, section_id, entry_id)
        ledger_value = LedgerProcessorSQL._rebuild_ledger_value_from_transactions(
            ledger_value, transactions, domain)
        LedgerAccessorSQL.save_ledger_values([ledger_value])

    @staticmethod
    def _rebuild_ledger_value_from_transactions(ledger_value, transactions, domain):
        track_load = ledger_load_counter("rebuild_ledger", domain)
        balance = 0
        for transaction in transactions:
            updated_values = _compute_ledger_values(balance, transaction)
            new_balance = updated_values.balance
            new_delta = updated_values.balance - balance
            if new_balance != transaction.updated_balance or new_delta != transaction.delta:
                transaction.delta = new_delta
                transaction.updated_balance = new_balance
                ledger_value.track_update(transaction)
            elif not transaction.is_saved():
                ledger_value.track_create(transaction)
            balance = new_balance
            track_load()
        if balance != ledger_value.balance or ledger_value.has_tracked_models():
            ledger_value.balance = balance

        return ledger_value

    def process_form_archived(self, form):
        from corehq.form_processor.parsers.ledgers.form import get_ledger_references_from_stock_transactions
        refs_to_rebuild = get_ledger_references_from_stock_transactions(form)
        case_ids = list({ref.case_id for ref in refs_to_rebuild})
        LedgerAccessorSQL.delete_ledger_transactions_for_form(case_ids, form.form_id)
        for ref in refs_to_rebuild:
            self.rebuild_ledger_state(**ref._asdict())

    def process_form_unarchived(self, form):
        from corehq.apps.commtrack.processing import process_stock
        result = process_stock([form])
        result.populate_models()
        LedgerAccessorSQL.save_ledger_values(result.models_to_save)

        refs_to_rebuild = {
            ledger_value.ledger_reference for ledger_value in result.models_to_save
        }
        for ref in refs_to_rebuild:
            self.rebuild_ledger_state(**ref._asdict())

        result.finalize()


def _compute_ledger_values(original_balance, transaction):
    if transaction.type == LedgerTransaction.TYPE_BALANCE:
        quantity = transaction.updated_balance
    elif transaction.type == LedgerTransaction.TYPE_TRANSFER:
        quantity = transaction.delta
    else:
        raise ValueError()

    ledger_values = compute_ledger_values(
        lambda: original_balance, transaction.readable_type, quantity
    )

    return ledger_values


def _get_ledger_transaction(lazy_original_balance, stock_report_helper, stock_trans, new_balance):
    return LedgerTransaction(
        form_id=stock_report_helper.form_id,
        server_date=stock_report_helper.server_date,
        report_date=stock_report_helper.timestamp,
        type=_report_type_to_ledger_type(stock_report_helper.report_type),
        case_id=stock_trans.case_id,
        section_id=stock_trans.section_id,
        entry_id=stock_trans.product_id,
        user_defined_type=stock_trans.subaction[:20] if stock_trans.subaction else None,
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
