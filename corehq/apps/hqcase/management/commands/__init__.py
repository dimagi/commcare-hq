

import logging
from optparse import make_option
from django.core.mail import send_mail
from django.core.management.base import  BaseCommand, NoArgsCommand
from casexml.apps.case.models import CommCareCase
from corehq.pillows import CasePillow

CHUNK_SIZE=500
POOL_SIZE = 15




class ReindexCommand(BaseCommand):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"
    pillow_type = None
    pillow_name = ""
    doc_class = None
    view_name = ""
    view_params = {}

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

        confirm_ptop = raw_input("""\tAre you sure you disabled run_ptop? """)
        if confirm_ptop != "yes":
            return

        confirm_alias = raw_input("""\tAre you sure you are not blowing away a production index?""")
        if confirm_alias != "yes":
            return

        #delete the existing index.
        pillow_instance = self.pillow_type()
        print "Deleting index"
        pillow_instance.delete_index()
        print "Recreating index"
        pillow_instance.create_index()
        pillow_instance.seen_types = {}
        print "Resetting %s Checkpoint" % self.pillow_name

        pillow_instance.reset_checkpoint()

        db = self.doc_class.get_db()
        start_num = 0

        print "starting fast tracked reindexing for %s" % self.pillow_name

        #chunk = db.view(self.view_name, reduce=False, limit=CHUNK_SIZE, skip=start_num)
        self.view_params.update(dict(limit=CHUNK_SIZE, skip=start_num)) #reduce=False
        chunk = db.view(self.view_name, **self.view_params)

        #though this might cause some superfluous reindexes of docs,
        # we're going to set the checkpoint BEFORE we start our operation so that any changes
        # that happen to cases while we're doing our reindexing would not get skipped once we
        # finish.
        pillow_instance.set_checkpoint({ 'seq': pillow_instance.couch_db.info()['update_seq'] } )
        def do_index(item):
            print "Processing: %s" % item['id']
            pillow_instance.processor(item, do_set_checkpoint=False)

        try:
            while len(chunk) > 0:
                for item in chunk:
                    pillow_instance.processor(item, do_set_checkpoint=False)
                start_num += CHUNK_SIZE
                print "Grabbing next chunk: %d" % start_num
                self.view_params['skip']=start_num
                chunk = db.view(self.view_name, **self.view_params)

            print "Index recreated - you may now restart run_ptop"
            send_mail('[commcare-hq] Pillowtop Case Reindex Complete',
                      "Case reindex complete for index %s" % pillow_instance.es_index,
                      'hq-noreply@dimagi.com', ['commcarehq-dev@dimagi.com'], fail_silently=True)
        except Exception, ex:
            logging.exception("%s pillowtop fast reindex failed: %s" % (self.pillow_name, ex))

