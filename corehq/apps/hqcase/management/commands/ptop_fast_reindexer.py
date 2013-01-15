from optparse import make_option
from django.core.management.base import NoArgsCommand
import logging
from django.core.mail import send_mail
from django.core.management.base import  BaseCommand
from casexml.apps.case.models import CommCareCase
from corehq.pillows import CasePillow, XFormPillow
from couchforms.models import XFormInstance
from dimagi.utils.logging import notify_exception

CHUNK_SIZE=500
POOL_SIZE = 15


class PtopReindexer(NoArgsCommand):
    help = "View based elastic reindexer"
    option_list = NoArgsCommand.option_list + (
        make_option('--resume',
                    action='store',
                    dest='purge',
                    default=False,
                    help='Resume, do not delete existing index data'),
    )


    doc_class = None
    view_name = None
    pillow_class = None


    def custom_filter(self, view_row):
        """
        Custom filter if you want to do additional filtering based on the view

        Return true if to index, false if to SKIP
        """
        return True


    def handle(self, *args, **options):
        confirm = raw_input("""
    ### %s Fast Reindex !!! ###
    You have requested to do an elastic index reset via fast track.
    This will IRREVERSIBLY REMOVE
    ALL index data in the case index and will take a while to reload.
    Are you sure you want to do this. Also you MUST have run_ptop disabled for this to run.

    Type 'yes' to continue, or 'no' to cancel: """ % self.doc_class.__name__)

        if confirm != 'yes':
            print "\tReset cancelled."
            return

        confirm_ptop = raw_input("""\tAre you sure you disabled run_ptop? """)
        if confirm_ptop != "yes":
            return

        confirm_alias = raw_input("""\tAre you sure you are not blowing away a production index?""")
        if confirm_alias != "yes":
            return


        #delete the existing index.
        pillow = self.pillow_class()
        print "Deleting index"
        pillow.delete_index()
        print "Recreating index"
        pillow.create_index()
        pillow.seen_types = {}
        print "Resetting %s Checkpoint" % self.doc_class.__name__
        pillow.reset_checkpoint()

        db = self.doc_class.get_db()
        start_num = 0

        print "starting fast tracked reindexing"
        chunk = db.view(self.view_name, reduce=False, limit=CHUNK_SIZE, skip=start_num)

        #though this might cause some superfluous reindexes of docs,
        # we're going to set the checkpoint BEFORE we start our operation so that any changes
        # that happen to cases while we're doing our reindexing would not get skipped once we
        # finish.
        pillow.set_checkpoint({ 'seq': pillow.couch_db.info()['update_seq'] } )
        def do_index(item):
            print "Processing: %s" % item['id']
            pillow.processor(item, do_set_checkpoint=False)

        try:
            while len(chunk) > 0:
                for item in chunk:
                    if not self.custom_filter(item):
                        continue
                    pillow.processor(item, do_set_checkpoint=False)
                start_num += CHUNK_SIZE
                print "Grabbing next chunk: %d" % start_num
                chunk = db.view(self.view_name, reduce=False, limit=CHUNK_SIZE, skip=start_num)

            print "Index recreated - you may now restart run_ptop"
            send_mail('[commcare-hq] Pillowtop %s Reindex Complete' % self.doc_class.__name__,
                      "Case reindex complete for index %s - it may now be aliased" % pillow.es_index,
                      'hq-noreply@dimagi.com', ['commcarehq-dev@dimagi.com'], fail_silently=True)
        except Exception, ex:
            notify_exception("XForm pillowtop fast reindex failed: %s" % ex)

