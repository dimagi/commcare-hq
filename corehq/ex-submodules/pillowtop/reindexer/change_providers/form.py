from corehq.apps.domain.models import Domain
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, doc_type_to_state
from corehq.form_processor.change_publishers import change_meta_from_sql_form
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.util.couch_helpers import MultiKeyViewArgsProvider
from corehq.util.pagination import paginate_function, ArgsListProvider
from couchforms.models import XFormInstance, all_known_formlike_doc_types
from pillowtop.feed.interface import Change
from pillowtop.reindexer.change_providers.composite import CompositeChangeProvider
from pillowtop.reindexer.change_providers.interface import ChangeProvider


class CouchXFormDomainChangeProvider(ChangeProvider):
    def __init__(self, domains, chunk_size=1000):
        self.domains = domains
        self.chunk_size = chunk_size

    def iter_all_changes(self, start_from=None):
        if not self.domains:
            return

        def data_function(**view_kwargs):
            return XFormInstance.get_db().view('by_domain_doc_type_date/view', **view_kwargs)

        keys = []
        doc_types = all_known_formlike_doc_types()
        for domain in self.domains:
            for doc_type in doc_types:
                keys.append([domain, doc_type])

        args_provider = MultiKeyViewArgsProvider(keys, include_docs=True, chunk_size=self.chunk_size)

        for row in paginate_function(data_function, args_provider):
            yield Change(
                id=row['id'],
                sequence_id=None,
                document=row.get('doc'),
                deleted=False,
                document_store=None
            )


class SqlDomainXFormChangeProvider(ChangeProvider):

    def __init__(self, domains, chunk_size=1000):
        self.domains = list(domains)
        self.chunk_size = chunk_size

    def iter_all_changes(self, start_from=None):
        if not self.domains:
            return

        for form_id_chunk in self._iter_form_id_chunks():
            for form in FormAccessorSQL.get_forms(form_id_chunk):
                yield Change(
                    id=form.form_id,
                    sequence_id=None,
                    document=form.to_json(),
                    deleted=False,
                    metadata=change_meta_from_sql_form(form),
                    document_store=None,
                )

    def _iter_form_id_chunks(self):
        kwargs = []
        for domain in self.domains:
            for doc_type in doc_type_to_state:
                kwargs.append({'domain': domain, 'type_': doc_type})

        args_provider = ArgsListProvider(kwargs)

        data_function = FormAccessorSQL.get_form_ids_in_domain_by_type
        chunk = []
        for form_id in paginate_function(data_function, args_provider):
            chunk.append(form_id)
            if len(chunk) >= self.chunk_size:
                yield chunk
                chunk = []

        if chunk:
            yield chunk


def get_domain_form_change_provider(domains):
    sql_domains = {domain for domain in domains if should_use_sql_backend(domain)}
    couch_domains = set(domains) - sql_domains

    return CompositeChangeProvider([
        SqlDomainXFormChangeProvider(sql_domains),
        CouchXFormDomainChangeProvider(couch_domains),
    ])
