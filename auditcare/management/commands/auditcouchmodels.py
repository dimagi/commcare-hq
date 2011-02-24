from django.core.management.base import LabelCommand
from couchdbkit.consumer import Consumer
import logging
import time
from dimagi.utils.couch.database import get_db

class Command(LabelCommand):
    help = "Listens for patient conflicts and resolves them."
    args = ""
    label = ""

    def handle(self, *args, **options):
        db = get_db()
        seq = db.info()['committed_update_seq']
        def audit_couch_save(line):
            try:
                print "Change: id: %s seq: %d" % (line['id'], line['seq'])
                #doc_id = line['id']
                seq=line['seq']
                print "\t*** updating sequence %d" % seq
                #doc = db.open_doc(doc_id)
                doc = line['doc']
                if doc.has_key('doc_type'):
                    print "\t%s: %s" % (doc['doc_type'], doc['_rev'])
            except:
                pass

        c = Consumer(db)



        # Go into receive loop waiting for any conflicting patients to
        # come in.
        while True:
            try:
                c.wait(heartbeat=5000,cb=audit_couch_save, since=seq,include_docs=True)
                print "current seq: %d" % seq
            except Exception, e:
                time.sleep(10)
                logging.warn("caught exception in conflict resolver: %s, sleeping and restarting" % e)
                print "regular exception %s" %(e)
            except KeyboardInterrupt:
                logging.info("Received keyboard interrupt, exiting.")
                print "keyboard interrupt"
                break


    def __del__(self):
        pass
