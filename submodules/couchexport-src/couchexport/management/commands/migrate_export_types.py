from django.core.management.base import LabelCommand, CommandError
from couchexport.models import SavedExportSchema
from optparse import make_option

class Command(LabelCommand):
    help = "Migrates over custom exports by adding a default type property if not present."
    args = "default_type"
    label = "default type"
    
    option_list = LabelCommand.option_list + \
        (make_option('--dryrun', action='store_true', dest='dryrun', default=False,
            help="Don't do the actual migration, just print the output"),)

    
    def handle(self, *args, **options):
        if len(args) != 1: raise CommandError("Syntax: ./manage.py migrate_export_types [default type]!")
        
        default_type = args[0]
        for export in SavedExportSchema.view("couchexport/saved_export_schemas", include_docs=True):
            if not export.type:
                print "migrating %s" % export
                export.type = default_type
                if not options['dryrun']:
                    export.save()
        print "Done!" 
                
