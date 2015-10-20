from django.core.management.base import LabelCommand, CommandError
from couchexport.groupexports import export_for_group

class Command(LabelCommand):
    help = "Runs an export based on a supplied configuration."
    args = "<id>, <output_location>"
    label = "Id of the saved export h, output directory for export files (use 'couch' for couch-based storage)."
     
    def handle(self, *args, **options):
        if len(args) < 2: raise CommandError('Please specify %s.' % self.label)
            
        export_id = args[0]
        output_dir = args[1]
        export_for_group(export_id, output_dir)
                