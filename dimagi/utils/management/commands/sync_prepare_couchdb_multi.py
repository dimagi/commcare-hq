from gevent import monkey
monkey.patch_all()
from restkit.session import set_session
set_session("gevent")

from django.db.models import get_apps
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from datetime import datetime
from gevent.pool import Pool
import logging
import time
from django.conf import settings
setattr(settings, 'COUCHDB_TIMEOUT', 999999)
from couchdbkit.ext.django.loading import couchdbkit_handler
from dimagi.utils.couch.database import get_db


POOL_SIZE = getattr(settings, 'PREINDEX_POOL_SIZE', 8)
POOL_WAIT = getattr(settings, 'PREINDEX_POOL_WAIT', 10)
MAX_TRIES = getattr(settings, 'PREINDEX_MAX_TRIES', 3)

def do_sync(app_index):
    """
    Get the app for the given index.
    For multiprocessing can't pass a complex object hence the call here...again
    """
    #sanity check:
    try:
        app = get_apps()[app_index]
        couchdbkit_handler.sync(app, verbosity=2, temp='tmp')
    except Exception, ex:
        print "Exception running sync, but ignoring.\n\tapp=%s\n\t%s" % (app, ex)
        return "%s-error" % app_index
    print "preindex %s complete" % app_index
    return app_index

class Command(BaseCommand):
    help = 'Sync design docs to temporary ids...but multithreaded'

    def handle(self, *args, **options):


        start = datetime.utcnow()
        if len(args) == 0:
            num_pool = POOL_SIZE
        else:
            num_pool = int(args[0])

        if len(args) > 1:
            username = args[1]
        else:
            username = 'unknown'

        pool = Pool(num_pool)

        apps = get_apps()

        completed = set()
        app_ids = set(range(len(apps)))
        for app_id in sorted(app_ids.difference(completed)):
            #keep trying all the preindexes until they all complete satisfactorily.
            print "Trying to preindex view (%d/%d) %s" % (app_id, len(apps), apps[app_id])
            pool.spawn(do_sync, app_id)

        # sshhhhhh: if we're using HQ also preindex the couch apps
        # this could probably be multithreaded too, but leaving for now
        try:
            from corehq.couchapps import sync_design_docs
        except ImportError:
            pass
        else:
            sync_design_docs(get_db(), temp="tmp")

        print "All apps loaded into jobs, waiting..."
        pool.join()
        print "All apps reported complete."

        #Git info
        message = "Preindex results:\n"
        message += "\tInitiated by: %s\n" % username

        delta = datetime.utcnow() - start
        message += "Total time: %d seconds" % delta.seconds
        print message

        #todo: customize this more for other users
        send_mail('[commcare-hq] Preindex Complete', message, 'hq-noreply@dimagi.com', ['commcarehq-dev@dimagi.com'], fail_silently=True)





