from django.core.management.base import  BaseCommand
from casexml.apps.case.models import CommCareCase
from pillows import CasePillow

CHUNK_SIZE=500
POOL_SIZE = 15




class Command(BaseCommand):
    help = "Prints the paths of all the static files"

    def handle(self, *args, **options):
        confirm = raw_input("""
    You have requested to do a case elastic index reset via fast track.
    This will IRREVERSIBLY REMOVE
    ALL index data in the case index and will take a while to reload.
    Are you sure you want to do this. Also you MUST have run_ptop disabled for this to run.

    Type 'yes' to continue, or 'no' to cancel: """)

        if confirm != 'yes':
            print "Reset cancelled."
            return

        confirm_ptop = raw_input("""Are you sure you disabled run_ptop? """)
        if confirm_ptop != "yes":
            return


        #delete the existing index.
        casepillow = CasePillow()
        print "Deleting index"
        casepillow.delete_index()
        print "Recreating index"
        casepillow.create_index()
        print "Resetting CasePillow Checkpoint"
        casepillow.reset_checkpoint()

        print "Index recreated - you may now restart run_ptop"

# view based reindexing is going to be commented out till we figure out what is up with indexing
#       proceed with fast track by going through the docs 1 by 1
#        db = CommCareCase.get_db()
#        start_num = 0

# exceptions with inconsistent types - namely the @type #text attributed fields.
#        print "starting fast tracked reindexing"
#        chunk = db.view('case/by_owner', reduce=False, limit=CHUNK_SIZE, skip=start_num)
#
#        def do_index(item):
#            print "Processing: %s" % item['id']
#            casepillow.processor(item, do_set_checkpoint=False)
#
#        while chunk != []:
#            for item in chunk:
#                casepillow.processor(item, do_set_checkpoint=False)
#            start_num += CHUNK_SIZE
#            print "Grabbing next chunk: %d" % start_num
#            chunk = db.view('case/by_owner', reduce=False, limit=CHUNK_SIZE, skip=start_num)

