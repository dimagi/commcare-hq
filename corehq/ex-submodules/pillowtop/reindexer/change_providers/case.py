from casexml.apps.case.models import CommCareCase
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.change_providers import _sql_case_to_change
from corehq.form_processor.utils.general import should_use_sql_backend
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
        case_ids = CaseAccessorSQL.get_case_ids_in_domain(self.domain)
        for case in CaseAccessorSQL.get_cases(case_ids):
            yield _sql_case_to_change(case)


def get_domain_case_change_provider(domains):
    change_providers = []
    for domain in domains:
        if should_use_sql_backend(domain):
            change_providers.append(SqlDomainCaseChangeProvider(domain))
        else:
            change_providers.append(get_couch_domain_case_change_provider(domain))
    return CompositeChangeProvider(change_providers)
