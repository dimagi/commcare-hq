from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL, LedgerAccessorSQL
from corehq.form_processor.change_publishers import (
    change_meta_from_sql_case, change_meta_from_sql_form,
    change_meta_from_ledger_v2, change_meta_from_ledger_v1
)
from pillowtop.feed.interface import Change
from pillowtop.reindexer.change_providers.interface import ChangeProvider


class SqlCaseChangeProvider(ChangeProvider):

    def __init__(self, chunk_size=500):
        self.chunk_size = chunk_size

    def iter_all_changes(self, start_from=None):
        for case in CaseAccessorSQL.get_all_cases_modified_since(start_from, chunk_size=self.chunk_size):
            yield _sql_case_to_change(case)


def _sql_case_to_change(case):
    return Change(
        id=case.case_id,
        sequence_id=None,
        document=case.to_json(),
        deleted=False,
        metadata=change_meta_from_sql_case(case),
        document_store=None,
    )


class SqlFormChangeProvider(ChangeProvider):

    def __init__(self, chunk_size=500):
        self.chunk_size = chunk_size

    def iter_all_changes(self, start_from=None):
        for form in FormAccessorSQL.get_all_forms_received_since(start_from, chunk_size=self.chunk_size):
            yield _sql_form_to_change(form)


def _sql_form_to_change(form):
    return Change(
        id=form.form_id,
        sequence_id=None,
        document=form.to_json(),
        deleted=False,
        metadata=change_meta_from_sql_form(form),
        document_store=None,
    )


class LedgerV2ChangeProvider(ChangeProvider):

    def __init__(self, chunk_size=500):
        self.chunk_size = chunk_size

    def iter_all_changes(self, start_from=None):
        for ledger in LedgerAccessorSQL.get_all_ledgers_modified_since(start_from, chunk_size=self.chunk_size):
            yield _ledger_v2_to_change(ledger)


def _ledger_v2_to_change(ledger_value):
    return Change(
        id=ledger_value.ledger_reference.as_id(),
        sequence_id=None,
        document=ledger_value.to_json(),
        deleted=False,
        metadata=change_meta_from_ledger_v2(ledger_value),
        document_store=None,
    )


class DjangoModelChangeProvider(ChangeProvider):

    def __init__(self, model_class, model_to_change_fn, chunk_size=500):
        self.model_class = model_class
        self.model_to_change_fn = model_to_change_fn
        self.chunk_size = chunk_size

    def iter_all_changes(self, start_from=None):
        from django.core.paginator import Paginator
        from django.core.paginator import EmptyPage

        model_list = self.model_class.objects.all()
        paginator = Paginator(model_list, self.chunk_size)

        page = 0
        while True:
            page += 1
            try:
                for model in paginator.page(page):
                    yield self.model_to_change_fn(model)
            except EmptyPage:
                return


def _ledger_v1_to_change(stock_state):
    return Change(
        id=stock_state.pk,
        sequence_id=None,
        document=stock_state.to_json(),
        deleted=False,
        metadata=change_meta_from_ledger_v1(stock_state),
        document_store=None,
    )


class DjangoModelChangeProvider(ChangeProvider):

    def __init__(self, model_class, model_to_change_fn, chunk_size=500):
        self.model_class = model_class
        self.model_to_change_fn = model_to_change_fn
        self.chunk_size = chunk_size

    def iter_all_changes(self, start_from=None):
        from django.core.paginator import Paginator
        from django.core.paginator import EmptyPage

        model_list = self.model_class.objects.all()
        paginator = Paginator(model_list, self.chunk_size)

        page = 1
        while True:
            try:
                for model in paginator.page(page):
                    yield self.model_to_change_fn(model)
            except EmptyPage:
                return


def _stock_state_to_change(stock_state):
    return Change(
        id=stock_state.pk,
        sequence_id=None,
        document=stock_state.to_json(),
        deleted=False,
        metadata=change_meta_from_stock_state(stock_state),
        document_store=None,
    )
