import itertools

from corehq.util.doc_processor.interface import DocumentProvider
from pillowtop.reindexer.change_providers.interface import ChangeProvider


class CompositeChangeProvider(ChangeProvider):
    """Change Provider of Change Providers
    """

    def __init__(self, change_providers):
        self.change_providers = change_providers

    def iter_all_changes(self, start_from=None):
        return itertools.chain(*[change_provider.iter_all_changes() for change_provider in self.change_providers])


class CompositeDocProvider(DocumentProvider):

    def __init__(self, doc_providers, iteration_key):
        self.iteration_key = iteration_key
        self.doc_providers = doc_providers

    def get_document_iterator(self, *args, **kwargs):
        return itertools.chain(*[doc_provider.get_document_iterator(*args, **kwargs) for doc_provider in self.doc_providers])

    def get_total_document_count(self):
        return sum([dc.get_total_document_count() for dc in self.doc_providers])
