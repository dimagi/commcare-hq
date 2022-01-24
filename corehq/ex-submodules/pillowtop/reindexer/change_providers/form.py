from corehq.form_processor.change_publishers import change_meta_from_sql_form
from corehq.form_processor.models import XFormInstance
from corehq.util.pagination import paginate_function, ArgsListProvider
from pillowtop.feed.interface import Change
from pillowtop.reindexer.change_providers.interface import ChangeProvider


class SqlDomainXFormChangeProvider(ChangeProvider):

    def __init__(self, domains, chunk_size=1000):
        self.domains = list(domains)
        self.chunk_size = chunk_size

    def iter_all_changes(self, start_from=None):
        if not self.domains:
            return

        for form_id_chunk in self._iter_form_id_chunks():
            for form in XFormInstance.objects.get_forms(form_id_chunk):
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
            for doc_type in XFormInstance.DOC_TYPE_TO_STATE:
                kwargs.append({'domain': domain, 'doc_type': doc_type})

        args_provider = ArgsListProvider(kwargs)

        data_function = XFormInstance.objects.get_form_ids_in_domain
        chunk = []
        for form_id in paginate_function(data_function, args_provider):
            chunk.append(form_id)
            if len(chunk) >= self.chunk_size:
                yield chunk
                chunk = []

        if chunk:
            yield chunk


def get_domain_form_change_provider(domains):
    return SqlDomainXFormChangeProvider(domains)
