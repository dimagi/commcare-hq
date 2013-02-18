from django.core.management.base import LabelCommand
from django.conf import settings
from django.db import models
from dimagi.utils.couch.database import get_db
from couchdbkit.consumer import Consumer
import logging
import time
from dimagi.utils.couch.changes import Change
from sofabed.forms.models import Checkpoint
from corehq.apps.domainsync.config import global_config
from couchdbkit.ext.django.loading import CouchdbkitHandler
from django.core.exceptions import ImproperlyConfigured
from corehq.couchapps import sync_design_docs

FILTER_FORMS_WITH_META = "forms/xforms_with_meta"
CHECKPOINT_FREQUENCY = 100
CHECKPOINT_ID = "domainsync_checkpoint"

domainsync_counter = 0

# this is based heavily on sofabed
class Command(LabelCommand):
    help = "Listens for documents and sync them between domains."
    args = ""
    label = ""
     
    def handle(self, *args, **options):
        db = get_db()
        c = Consumer(db)
        
        # sync design docs to the target db
        # lots of source diving to figure out this magic
        new_dbs = [(app, global_config.database.uri) for app, _ in settings.COUCHDB_DATABASES]
        couchdbkit_handler = CouchdbkitHandler(new_dbs)
        for app, _ in new_dbs:
            try:
                couchdbkit_handler.sync(models.get_app(app))
            except ImproperlyConfigured:
                # if django doesn't think this is an app it throws this error
                # this is probably fine
                pass
        
        # also sync couchapps
        sync_design_docs(global_config.database)
        
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

        # Go into receive loop waiting for any new docs to come in
        while True:
            try:
                last_checkpoint = Checkpoint.get_last_checkpoint(CHECKPOINT_ID)
                kwargs = {"heartbeat": 5000,
                          "cb": sync_if_necessary}
                if last_checkpoint is not None:
                    kwargs["since"] = last_checkpoint
                c.wait(**kwargs)
                       
            except Exception, e:
                time.sleep(10)
                logging.exception("caught exception in domain sync: %s, sleeping and restarting" % e)

    def __del__(self):
        pass
    
