from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, doc_type_to_state
from corehq.form_processor.change_publishers import change_meta_from_sql_form
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.util.pagination import paginate_function, ArgsListProvider
from couchforms.models import XFormInstance, all_known_formlike_doc_types
from pillowtop.feed.interface import Change
from pillowtop.reindexer.change_providers.composite import CompositeChangeProvider
from pillowtop.reindexer.change_providers.couch import CouchDomainDocTypeChangeProvider
from pillowtop.reindexer.change_providers.interface import ChangeProvider


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
        CouchDomainDocTypeChangeProvider(
            couch_db=XFormInstance.get_db(),
            domains=couch_domains,
            doc_types=all_known_formlike_doc_types()
        ),
    ])
