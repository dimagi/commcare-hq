from django.core.management.base import LabelCommand, CommandError
from couchexport.models import ExportSchema
import json
from couchexport.export import ExportConfiguration

class Command(LabelCommand):
    help = "Update all schemas to use the latest checkpoints."

    def handle(self, *args, **options):
        db = ExportSchema.get_db()

        def _get_all_indices():
            ret = db.view("couchexport/schema_checkpoints",
                          startkey=['by_timestamp'],
                          endkey=['by_timestamp', {}],
                          reduce=True,
                          group=True,
                          group_level=2)
            for row in ret:
                index = row['key'][1]
                try:
                    yield json.loads(index)
                except ValueError:
                    # ignore this for now - should just be garbage data
                    print "poorly formatted index key %s" % index

        for index in _get_all_indices():
            last = ExportSchema.last(index)
            if not last.timestamp:
                config = ExportConfiguration(db, index, disable_checkpoints=True)
                config.create_new_checkpoint()
                assert ExportSchema.last(index).timestamp
                print "set timestamp for %s" % index
            else:
                print "%s all set" % index
        