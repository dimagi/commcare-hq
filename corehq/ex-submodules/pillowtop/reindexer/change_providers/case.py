from casexml.apps.case.models import CommCareCase
from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor
from corehq.form_processor.change_publishers import change_meta_from_sql_case
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from pillowtop.feed.interface import Change
from pillowtop.reindexer.change_providers.composite import CompositeChangeProvider
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.change_providers.interface import ChangeProvider


def get_couch_domain_case_change_provider(domain):
    return CouchViewChangeProvider(
        couch_db=CommCareCase.get_db(),
        view_name='cases_by_owner/view',
        chunk_size=100,
        view_kwargs={
            'include_docs': True,
            'startkey': [domain],
            'endkey': [domain, {}, {}]
        }
    )


class SqlDomainCaseChangeProvider(ChangeProvider):

    def __init__(self, domain):
        self.domain = domain

    def iter_all_changes(self, start_from=None):
        for db_alias in get_db_aliases_for_partitioned_query():
            accessor = CaseReindexAccessor()
            cases = accessor.get_docs_for_domain(db_alias, self.domain, start_from)
            while cases:
                for case in cases:
                    yield _sql_case_to_change(case)

                start_from = case.server_modified_on
                last_id = case.id
                cases = accessor.get_docs_for_domain(db_alias, self.domain, start_from, last_doc_pk=last_id)


def get_domain_case_change_provider(domains):
    change_providers = []
    for domain in domains:
        if should_use_sql_backend(domain):
            change_providers.append(SqlDomainCaseChangeProvider(domain))
        else:
            change_providers.append(get_couch_domain_case_change_provider(domain))
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
