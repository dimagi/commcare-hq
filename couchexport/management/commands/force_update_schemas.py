from django.core.management.base import LabelCommand, CommandError
from couchexport.models import ExportSchema
from couchexport.export import ExportConfiguration
import json

class Command(LabelCommand):
    help = "Given a particular export index, all checkpoints referencing that " \
           "index to use the schema."
    args = "<index>"
    label = "Index of the export to use, or 'all' to include all exports"

    def handle(self, *args, **options):
        if len(args) < 1: raise CommandError('Please specify %s.' % self.label)
        index_in = args[0]
        if index_in == "all":
            to_update = ExportSchema.get_all_indices()
        else:
            to_update = [json.loads(index_in)]
        
        db = ExportSchema.get_db()
        for index in to_update:
            all_checkpoints = ExportSchema.get_all_checkpoints(index)
            config = ExportConfiguration(db, index, disable_checkpoints=True)
            latest = config.create_new_checkpoint()
            for cp in all_checkpoints:
                cp.schema = latest.schema
                cp.save()
            else:
                print "processed %s checkpoints matching %s" % (len(all_checkpoints), index)
