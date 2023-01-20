from django.core.management import call_command
from django.db.migrations import RunPython


class ReindexCouchViews(RunPython):
    """Reindex Couch DB views and Elasticsearch indexes

    Use as needed whenever Couch views are changed and need to be
    reindexed. This operation may take a long time, depending on what is
    being reindexed.

    It is planned for the Elasticsearch index building features to move
    to migration operations dedicated that purpose alone.
    See corehq/apps/es/migration_operations.py
    """

    def __init__(self):
        super().__init__(self.run, RunPython.noop)

    def deconstruct(self):
        return (self.__class__.__qualname__, [], {})

    def run(self, apps, schema_editor):
        call_command("preindex_everything", 8)
        call_command("sync_finish_couchdb_hq")
        call_command("ptop_es_manage", flip_all_aliases=True)
