import itertools

from pillowtop.reindexer.change_providers.interface import ChangeProvider


class CompositeChangeProvider(ChangeProvider):
    """Change Provider of Change Providers
    """
    def __init__(self, change_providers):
        self.change_providers = change_providers

    def iter_all_changes(self, start_from=None):
        return itertools.chain(*[change_provider.iter_all_changes() for change_provider in self.change_providers])
