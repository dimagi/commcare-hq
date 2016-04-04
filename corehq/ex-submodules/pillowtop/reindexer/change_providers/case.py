import itertools

from casexml.apps.case.models import CommCareCase
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.change_providers import _sql_case_to_change
from corehq.form_processor.utils.general import should_use_sql_backend
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.change_providers.interface import ChangeProvider


class CouchDomainCaseChangeProvider(CouchViewChangeProvider):
    def __init__(self, domain):
        self.document_class = CommCareCase
        self._couch_db = self.document_class.get_db()
        self._view_name = 'cases_by_owner/view'
        self._chunk_size = 100
        self._view_kwargs = {
            'include_docs': True,
            'startkey': [domain],
            'endkey': [domain, {}, {}]
        }


class SqlDomainCaseChangeProvider(ChangeProvider):

    def __init__(self, domain):
        self.domain = domain

    def iter_changes(self, start_from=None):
        case_ids = CaseAccessorSQL.get_case_ids_in_domain(self.domain)
        for case in CaseAccessorSQL.get_cases(case_ids):
            yield _sql_case_to_change(case)


class DomainCaseChangeProvider(ChangeProvider):
    """Returns all cases only for a list of domains
    """
    def __init__(self, domains):
        self.domains = domains
        self.change_providers = []

        for domain in self.domains:
            if should_use_sql_backend(domain):
                self.change_providers.append(SqlDomainCaseChangeProvider(domain))
            else:
                self.change_providers.append(CouchDomainCaseChangeProvider(domain))

    def iter_changes(self, start_from=None):
        return itertools.chain(*[change_provider.iter_changes() for change_provider in self.change_providers])
