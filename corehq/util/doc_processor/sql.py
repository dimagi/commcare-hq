from corehq.util.doc_processor.interface import DocumentProvider
from corehq.util.pagination import ResumableFunctionIterator, ArgsProvider


class SqlModelArgsProvider(ArgsProvider):
    def __init__(self, db_list):
        self.db_list = db_list

    def get_initial_args(self):
        return [self.db_list[0], None], {}

    def get_next_args(self, result, *last_args, **last_view_kwargs):
        if result:
            next_id = result.pk
            return [last_args[0], next_id], {}
        else:
            last_db = last_args[0]
            # skip databases already processed
            index = self.db_list.index(last_db) + 1
            self.db_list = self.db_list[index:]
            try:
                next_db = self.db_list[0]
            except IndexError:
                raise StopIteration

            return [next_db, None], {}


def resumable_sql_model_iterator(iteration_key, reindex_accessor, chunk_size=100, event_handler=None):
    """Perform one-time resumable iteration over documents

    Iteration can be efficiently stopped and resumed. The iteration may
    omit documents that are added after the iteration begins or resumes
    and may include deleted documents.

    :param iteration_key: A unique key identifying the iteration. This
    key will be used in combination with `doc_types` to maintain state
    about an iteration that is in progress. The state will be maintained
    indefinitely unless it is removed with `discard_state()`.
    :param reindex_accessor: A ``ReindexAccessor`` object.
    :param chunk_size: Number of documents to yield before updating the
    iteration checkpoint. In the worst case about this many documents
    that were previously yielded may be yielded again if the iteration
    is stopped and later resumed.
    """
    NULL = object()

    def data_function(from_db, filter_value, last_id=NULL):
        if last_id is NULL:
            # adapt to old iteration states
            last_id = filter_value
        return reindex_accessor.get_docs(from_db, last_id, limit=chunk_size)

    args_provider = SqlModelArgsProvider(reindex_accessor.sql_db_aliases)

    class ResumableModelIterator(ResumableFunctionIterator):
        def __iter__(self):
            for doc in super(ResumableModelIterator, self).__iter__():
                yield reindex_accessor.doc_to_json(doc)

    item_getter = reindex_accessor.get_doc

    return ResumableModelIterator(iteration_key, data_function, args_provider, item_getter, event_handler)


class SqlDocumentProvider(DocumentProvider):
    """Document provider for SQL documents.

    :param iteration_key: unique key to identify the document iterator
    :param reindex_accessor: A ``ReindexAccessor`` object
    """
    def __init__(self, iteration_key, reindex_accessor):
        """
        :type reindex_accessor: ReindexAccessor
        """
        self.iteration_key = iteration_key
        self.reindex_accessor = reindex_accessor

    def get_document_iterator(self, chunk_size, event_handler=None):
        return resumable_sql_model_iterator(
            self.iteration_key, self.reindex_accessor,
            chunk_size=chunk_size, event_handler=event_handler
        )

    def get_total_document_count(self):
        return sum(
            self.reindex_accessor.get_approximate_doc_count(from_db)
            for from_db in self.reindex_accessor.sql_db_aliases
        )
