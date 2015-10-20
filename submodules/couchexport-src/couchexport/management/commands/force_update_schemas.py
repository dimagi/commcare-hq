from django.core.management.base import LabelCommand, CommandError
from couchexport.models import ExportSchema
import json
from couchexport.tasks import rebuild_schemas

class Command(LabelCommand):
    help = "Given a particular export index, update all checkpoints " \
           "referencing that index to use the latest schema."
    args = "<index>"
    label = "Index of the export to use, or 'all' to include all exports"

    def handle(self, *args, **options):
        if len(args) < 1: raise CommandError('Please specify %s.' % self.label)
        index_in = args[0]
        if index_in == "all":
            to_update = ExportSchema.get_all_indices()
        else:
            to_update = [json.loads(index_in)]

        for index in to_update:
            processed = rebuild_schemas(index)
            print "processed %s checkpoints matching %s" % (processed, index)
