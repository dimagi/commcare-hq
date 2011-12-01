from django.core.management.base import LabelCommand
from dimagi.utils.couch.database import get_db
from couchdbkit.consumer import Consumer
import logging
import time
from dimagi.utils.couch.changes import Change
from couchforms.models import XFormInstance
from sofabed.forms.config import get_formdata_class
from django.db import transaction
from sofabed.forms.models import Checkpoint
from django.db.utils import DatabaseError
from sofabed.forms.exceptions import InvalidFormUpdateException
from corehq.apps.domainsync.config import global_config

FILTER_FORMS_WITH_META = "forms/xforms_with_meta"
CHECKPOINT_FREQUENCY = 100
CHECKPOINT_ID = "domainsync_checkpoint"

domainsync_counter = 0

# this is based heavily on sofabed
class Command(LabelCommand):
    help = "Listens for XFormInstance documents and sync them between domains."
    args = ""
    label = ""
     
    def handle(self, *args, **options):
        db = get_db()
        c = Consumer(db)
        
        def sync_if_necessary(line):
            try:
                change = Change(line)
                # don't bother with deleted or old documents
                if change.deleted or not change.is_current(db):
                    return 
                
                # get doc
                doc = get_db().get(change.id)
                
                # check if transforms, and if so, save to new domain/db
                transforms = global_config.get_transforms(doc)
                for transform in transforms:
                    global_config.save(transform)
                
                # update the checkpoint, somewhat arbitrarily
                global domainsync_counter
                domainsync_counter = domainsync_counter + 1
                if domainsync_counter % CHECKPOINT_FREQUENCY == 0:
                    Checkpoint.set_checkpoint(CHECKPOINT_ID, change.seq)
            
            except Exception, e:
                logging.exception("problem in domain sync for line: %s\n%s" % (line, e))
                raise
                
        last_checkpoint = Checkpoint.get_last_checkpoint(CHECKPOINT_ID)
        
        # Go into receive loop waiting for any new docs to come in
        while True:
            try:
                c.wait(heartbeat=5000, since=last_checkpoint, cb=sync_if_necessary)
                       
            except Exception, e:
                time.sleep(10)
                logging.exception("caught exception in domain sync: %s, sleeping and restarting" % e)

    def __del__(self):
        pass
    
