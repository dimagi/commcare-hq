from __future__ import absolute_import
from pillowtop.reindexer.change_providers.interface import ChangeProvider
from corehq.util.queries import paginated_queryset


class DjangoModelChangeProvider(ChangeProvider):

    def __init__(self, model_class, model_to_change_fn, chunk_size=500):
        self.model_class = model_class
        self.model_to_change_fn = model_to_change_fn
        self.chunk_size = chunk_size

    def iter_all_changes(self, start_from=None):
        model_list = self.model_class.objects.all()
        for model in paginated_queryset(model_list, self.chunk_size):
            yield self.model_to_change_fn(model)
