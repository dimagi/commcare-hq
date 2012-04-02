from django.core.management.base import LabelCommand, CommandError
from casexml.apps.case.models import CommCareCase
from optparse import make_option
from couchexport.models import SavedExportSchema


class Command(LabelCommand):
    help = "."
    args = ""
    label = ""
    
    option_list = LabelCommand.option_list + \
        (make_option('--dryrun', action='store_true', dest='dryrun', default=False,
            help="Don't do the actual migration, just print the output"),)

    def handle(self, *args, **options):
        if len(args) != 0: raise CommandError("This command doesn't expect arguments!")
            
        for case in CommCareCase.view("case/by_user", include_docs=True, reduce=False):
            print "migrating %s" % case
            if hasattr(case, 'domain') and hasattr(case, 'type'):
                case['#export_tag'] = ["domain", "type"]
            if not options["dryrun"]:
                case.save()
                print "migrated"
            else:
                print "nothing to do"
