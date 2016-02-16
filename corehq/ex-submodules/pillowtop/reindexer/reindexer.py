from pillowtop.pillow.interface import PillowRuntimeContext


class PillowReindexer(object):

    def __init__(self, pillow, change_provider):
        self.pillow = pillow
        self.change_provider = change_provider

    def reindex(self, start_from=None):
        reindexer_context = PillowRuntimeContext(do_set_checkpoint=False)
        for change in self.change_provider.iter_changes(start_from=start_from):
            self.pillow.processor(change, reindexer_context)
