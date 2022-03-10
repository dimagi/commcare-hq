from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor, iter_all_rows
from corehq.form_processor.change_publishers import change_meta_from_sql_case
from pillowtop.feed.interface import Change
from pillowtop.reindexer.change_providers.composite import CompositeChangeProvider
from pillowtop.reindexer.change_providers.interface import ChangeProvider


class SqlDomainCaseChangeProvider(ChangeProvider):

    def __init__(self, domain, limit_db_aliases=None):
        self.domain = domain
        self.limit_db_aliases = limit_db_aliases

    def iter_all_changes(self, start_from=None):
        accessor = CaseReindexAccessor(self.domain, limit_db_aliases=self.limit_db_aliases)
        for case in iter_all_rows(accessor):
            yield _sql_case_to_change(case)


def get_domain_case_change_provider(domains, limit_db_aliases=None):
    change_providers = []
    for domain in domains:
        change_providers.append(SqlDomainCaseChangeProvider(domain, limit_db_aliases=limit_db_aliases))
    return CompositeChangeProvider(change_providers)


def _sql_case_to_change(case):
    return Change(
        id=case.case_id,
        sequence_id=None,
        document=case.to_json(),
        deleted=False,
        metadata=change_meta_from_sql_case(case),
        document_store=None,
    )
