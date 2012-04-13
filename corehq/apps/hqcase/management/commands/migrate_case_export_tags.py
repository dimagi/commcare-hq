from django.core.management.base import LabelCommand, CommandError
from casexml.apps.case.models import CommCareCase
from optparse import make_option
from couchexport.models import SavedExportSchema
from dimagi.utils.couch.database import get_db


class Command(LabelCommand):
    help = "."
    args = ""
    label = ""
    
    option_list = LabelCommand.option_list + \
        (make_option('--dryrun', action='store_true', dest='dryrun', default=False,
            help="Don't do the actual migration, just print the output"),)

    def handle(self, *args, **options):
        if len(args) != 0: raise CommandError("This command doesn't expect arguments!")
            
        count = 0
        for line in get_db().view("case/by_user", reduce=False):
            case = CommCareCase.get(line["id"])
            if hasattr(case, 'domain') and hasattr(case, 'type'):
                if not "#export_tag" in case or case['#export_tag'] != ["domain", "type"]:
                    print "migrating case %s in domain %s" % (case.get_id, case.domain)
                    case['#export_tag'] = ["domain", "type"]
                    count += 1
                    if not options["dryrun"]:
                        case.save()
        prefix = "would have " if options["dryrun"] else ""
        print "%smigrated %s cases" % (prefix, count)
