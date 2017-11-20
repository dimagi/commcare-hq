from __future__ import absolute_import
from pillowtop.reindexer.change_providers.interface import ChangeProvider
from django.core.paginator import Paginator
from django.core.paginator import EmptyPage


class DjangoModelChangeProvider(ChangeProvider):

    def __init__(self, model_class, model_to_change_fn, chunk_size=500):
        self.model_class = model_class
        self.model_to_change_fn = model_to_change_fn
        self.chunk_size = chunk_size

    def iter_all_changes(self, start_from=None):

        model_list = self.model_class.objects.all()
        paginator = Paginator(model_list, self.chunk_size)

        page = 0
        while True:
            page += 1
            try:
                for model in paginator.page(page):
                    yield self.model_to_change_fn(model)
            except EmptyPage:
                return
