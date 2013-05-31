from gevent import monkey
monkey.patch_all()
from restkit.session import set_session
set_session("gevent")

from django.db.models import get_apps
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from datetime import datetime
from gevent.pool import Pool
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

        # same hack above for MVP
        try:
            from mvp_apps import sync_design_docs as mvp_sync
        except ImportError:
            pass
        else:
            mvp_sync(get_db(), temp="tmp")

        # same hack above for MVP
        try:
            from fluff.sync_couchdb import sync_design_docs as fluff_sync
        except ImportError:
            pass
        else:
            fluff_sync(temp="tmp")

        print "All apps loaded into jobs, waiting..."
        pool.join()
        print "All apps reported complete."

        message = "Preindex results:\n"
        message += "\tInitiated by: %s\n" % username

        delta = datetime.utcnow() - start
        message += "Total time: %d seconds" % delta.seconds
        print message

        send_mail('%s Preindex Complete' % settings.EMAIL_SUBJECT_PREFIX,
                  message,
                  settings.SERVER_EMAIL,
                  [x[1] for x in settings.ADMINS],
                  fail_silently=True)





