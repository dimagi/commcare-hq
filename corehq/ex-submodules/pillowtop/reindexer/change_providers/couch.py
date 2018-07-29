from __future__ import absolute_import
from __future__ import unicode_literals
from copy import copy
from corehq.util.couch_helpers import paginate_view, MultiKeyViewArgsProvider
from corehq.util.pagination import paginate_function
from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.feed.interface import Change
from pillowtop.reindexer.change_providers.interface import ChangeProvider


class CouchViewChangeProvider(ChangeProvider):
    """
    A ChangeProvider on top of a couch view. Lets you parameterize how you query
    the view and will then return an iterator over all the results of that view
    query.

    This is meant to eventually replace the logic in the PtopReindexer subclasses
    that currently deal with this.
    """

    def __init__(self, couch_db, view_name, chunk_size=100, view_kwargs=None):
        self._couch_db = couch_db
        self._view_name = view_name
        self._chunk_size = chunk_size
        self._view_kwargs = view_kwargs or {}

    def iter_all_changes(self, start_from=None):
        view_kwargs = copy(self._view_kwargs)
        view_kwargs['reduce'] = False  # required to paginate a view
        if start_from is not None:
            # todo: should we abstract out how the keys work inside this class?
            view_kwargs['startkey'] = start_from
        for row in paginate_view(self._couch_db, self._view_name, self._chunk_size, **view_kwargs):
            # todo: if include_docs isn't specified then this will make one request to couch per row
            # to get the documents. In the future we will likely need to add chunking
            yield Change(id=row['id'], sequence_id=None, document=row.get('doc'), deleted=False,
                         document_store=CouchDocumentStore(self._couch_db))


class CouchDomainDocTypeChangeProvider(ChangeProvider):
    def __init__(self, couch_db, domains, doc_types, chunk_size=1000, event_handler=None):
        self.domains = domains
        self.doc_types = doc_types
        self.chunk_size = chunk_size
        self.couch_db = couch_db
        self.event_handler = event_handler

    def iter_all_changes(self, start_from=None):
        if not self.domains:
            return

        def data_function(**view_kwargs):
            return self.couch_db.view('by_domain_doc_type_date/view', **view_kwargs)

        keys = []
        for domain in self.domains:
            for doc_type in self.doc_types:
                keys.append([domain, doc_type])

        args_provider = MultiKeyViewArgsProvider(keys, include_docs=True, chunk_size=self.chunk_size)

        for row in paginate_function(data_function, args_provider, event_handler=self.event_handler):
            yield Change(
                id=row['id'],
                sequence_id=None,
                document=row.get('doc'),
                deleted=False,
                document_store=None
            )
