from datetime import datetime
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.change_publishers import change_meta_from_sql_case
from pillowtop.feed.interface import Change
from pillowtop.reindexer.change_providers.interface import ChangeProvider


class SqlCaseChangeProvider(ChangeProvider):

    def __init__(self, chunk_size=500):
        self.chunk_size = chunk_size

    def iter_changes(self, start_from=None):
        start_from = start_from or datetime.min
        batch = CaseAccessorSQL.get_all_cases_modified_since(start_from, limit=self.chunk_size)
        while len(batch) == self.chunk_size:
            for case in batch:
                yield _sql_case_to_change(case)
                # todo: assumes cases are sorted by modified date -- may not be valid in a sharded setup
                next_start_from = case.server_modified_on
            # make sure we are making progress
            assert next_start_from > start_from
            start_from = next_start_from
            batch = CaseAccessorSQL.get_all_cases_modified_since(start_from, limit=self.chunk_size)

        # last batch
        for case in batch:
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
