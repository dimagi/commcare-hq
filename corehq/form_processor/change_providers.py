from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL
from corehq.form_processor.change_publishers import change_meta_from_sql_case, change_meta_from_sql_form
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
