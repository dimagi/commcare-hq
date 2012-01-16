from django.core.management.base import LabelCommand, CommandError
from couchexport.models import GroupExportConfiguration
from couchdbkit.exceptions import ResourceNotFound
from couchexport.export import export_new
import os

class Command(LabelCommand):
    help = "Runs an export based on a supplied configuration."
    args = "<id>, <output_directory>"
    label = "Id of the saved export configuration, output directory for export files."
     
    def handle(self, *args, **options):
        if len(args) < 2: raise CommandError('Please specify %s.' % self.label)
            
        export_id = args[0]
        output_dir = args[1]
        try:
            config = GroupExportConfiguration.get(export_id)
        except ResourceNotFound:
            raise CommandError("Couldn't find an export with id %s" % export_id)
        
        for export in config.full_exports:
            filename = export.filename
            with open(os.path.join(output_dir, filename), "wb") as f:
                print "exporting %s to %s" % (export.name, output_dir)
                export_new(export.index, f, format=export.format)
                