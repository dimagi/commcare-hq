from django.core.management.base import LabelCommand
from couchexport.models import ExportSchema
from couchexport.export import ExportConfiguration

class Command(LabelCommand):
    help = "Update all schemas to use the latest checkpoints."

    def handle(self, *args, **options):
        db = ExportSchema.get_db()
        for index in ExportSchema.get_all_indices():
            last = ExportSchema.last(index)
            if not last.timestamp:
                config = ExportConfiguration(db, index, disable_checkpoints=True)
                config.create_new_checkpoint()
                assert ExportSchema.last(index).timestamp
                print "set timestamp for %s" % index
            else:
                print "%s all set" % index
