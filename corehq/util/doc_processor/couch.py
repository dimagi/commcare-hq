from __future__ import print_function
from __future__ import absolute_import
from couchdbkit import ResourceNotFound

from corehq.util.couch_helpers import MultiKeyViewArgsProvider
from corehq.util.doc_processor.interface import DocumentProvider, ProcessorProgressLogger
from corehq.util.pagination import ResumableFunctionIterator


def resumable_view_iterator(db, iteration_key, view_name, view_keys, chunk_size=100, view_event_handler=None):
    """Perform one-time resumable iteration over a CouchDB View

    Iteration can be efficiently stopped and resumed. The iteration may
    omit documents that are added after the iteration begins or resumes
    and may include deleted documents.

    :param db: Couchdb database.
    :param iteration_key: A unique key identifying the iteration. This
    key will be used to maintain state about an iteration that is in progress.
    The state will be maintained indefinitely unless it is removed with `discard_state()`.
    :param view_name: The name of the CouchDB view to query
    :param view_keys: List of view keys to use when querying the view.
    :param chunk_size: Number of documents to yield before updating the
    iteration checkpoint. In the worst case about this many documents
    that were previously yielded may be yielded again if the iteration
    is stopped and later resumed.
    """

    def data_function(**view_kwargs):
        view_kwargs["limit"] = chunk_size
        return db.view(view_name, **view_kwargs)

    args_provider = MultiKeyViewArgsProvider(view_keys, include_docs=True)
    args_provider.initial_view_kwargs.pop("limit")

    class ResumableDocsIterator(ResumableFunctionIterator):
        def __iter__(self):
            for result in super(ResumableDocsIterator, self).__iter__():
                yield result['doc']

    def item_getter(doc_id):
        try:
            return {'doc': db.get(doc_id)}
        except ResourceNotFound:
            pass

    return ResumableDocsIterator(iteration_key, data_function, args_provider, item_getter, view_event_handler)


def resumable_docs_by_type_iterator(db, doc_types, iteration_key, chunk_size=100,
                                    view_event_handler=None, domain=None):
    """Perform one-time resumable iteration over documents by type

    Iteration can be efficiently stopped and resumed. The iteration may
    omit documents that are added after the iteration begins or resumes
    and may include deleted documents.

    :param db: Couchdb database.
    :param doc_types: A list of doc type names to iterate on (can't be empty).
    :param iteration_key: A unique key identifying the iteration. This
    key will be used to maintain state about an iteration that is in progress.
    The state will be maintained indefinitely unless it is removed with `discard_state()`.
    :param chunk_size: Number of documents to yield before updating the
    iteration checkpoint. In the worst case about this many documents
    that were previously yielded may be yielded again if the iteration
    is stopped and later resumed.
    :param domain: If the domain is specified only iterate over docs for that domain
    """

    view_name = 'by_domain_doc_type_date/view' if domain else 'all_docs/by_doc_type'

    def _get_key(doc_type):
        if domain:
            return [domain, doc_type]
        return [doc_type]

    keys = [_get_key(doc_type) for doc_type in doc_types]

    return resumable_view_iterator(db, iteration_key, view_name, keys, chunk_size, view_event_handler)


class CouchProcessorProgressLogger(ProcessorProgressLogger):
    """
    :param doc_types: List of doc_types that are being processed
    """
    def __init__(self, doc_types):
        self.doc_types = doc_type_tuples_to_list(doc_types)

    def progress_starting(self, total, previously_visited):
        print("Processing {} documents{}: {}...".format(
            total,
            " (~{} already processed)".format(previously_visited) if previously_visited else "",
            ", ".join(self.doc_types)
        ))


class CouchDocumentProvider(DocumentProvider):
    """Document provider for couch documents.

    All documents must live in the same couch database.

    :param iteration_key: unique key to identify the document iterator. Must be unique
    across all document iterators.
    :param doc_type_tuples: An ordered sequence where each item in the sequence should be
    either a doc type class or a tuple ``(doc_type_name_string, doc_type_class)``
    if the doc type name is different from the model class name.
    Note that the order of the sequence should never change while the iteration is
    in progress to avoid skipping doc types.
    """
    def __init__(self, iteration_key, doc_type_tuples, domain=None):
        self.iteration_key = iteration_key
        self.domain = domain

        assert isinstance(doc_type_tuples, list)

        self.doc_types = doc_type_tuples_to_list(doc_type_tuples)
        self.doc_type_map = doc_type_tuples_to_dict(doc_type_tuples)

        if len(doc_type_tuples) != len(self.doc_type_map):
            raise ValueError("Invalid (duplicate?) doc types")

        self.couchdb = next(iter(self.doc_type_map.values())).get_db()
        couchid = lambda db: getattr(db, "dbname", id(db))
        dbid = couchid(self.couchdb)
        assert all(couchid(m.get_db()) == dbid for m in self.doc_type_map.values()), \
            "documents must live in same couch db: %s" % repr(self.doc_type_map)

        if domain:
            for doc_class in self.doc_type_map.values():
                properties_by_key = doc_class._properties_by_key
                assert 'domain' in properties_by_key, "{} does not have a 'domain' property".format(doc_class)

    def get_document_iterator(self, chunk_size, event_handler=None):
        return resumable_docs_by_type_iterator(
            self.couchdb, self.doc_types, self.iteration_key,
            chunk_size=chunk_size, view_event_handler=event_handler,
            domain=self.domain
        )

    def get_total_document_count(self):
        from corehq.dbaccessors.couchapps.all_docs import get_doc_count_by_type, get_doc_count_by_domain_type
        if self.domain:
            return sum(
                get_doc_count_by_domain_type(self.couchdb, self.domain, doc_type)
                for doc_type in self.doc_type_map
            )
        else:
            return sum(
                get_doc_count_by_type(self.couchdb, doc_type)
                for doc_type in self.doc_type_map
            )


class CouchViewDocumentProvider(DocumentProvider):
    def __init__(self, couchdb, iteration_key, view_name, view_keys):
        self.couchdb = couchdb
        self.iteration_key = iteration_key
        self.view_name = view_name
        self.view_keys = view_keys

    def get_document_iterator(self, chunk_size, event_handler=None):
        return resumable_view_iterator(
            self.couchdb, self.iteration_key, self.view_name, self.view_keys,
            chunk_size=chunk_size, view_event_handler=event_handler
        )

    def get_total_document_count(self):
        return -1


def doc_type_tuples_to_dict(doc_types):
    return dict(
        t if isinstance(t, tuple) else (t.__name__, t) for t in doc_types
    )


def doc_type_tuples_to_list(doc_types):
    return sorted(doc_type_tuples_to_dict(doc_types))
