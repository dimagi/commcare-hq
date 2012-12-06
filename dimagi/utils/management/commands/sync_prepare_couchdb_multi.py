from django.db.models import get_apps
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from datetime import datetime
from gevent.pool import Pool
import logging
import time
from django.conf import settings
setattr(settings, 'COUCHDB_TIMEOUT', 1)
from couchdbkit.ext.django.loading import couchdbkit_handler
from dimagi.utils.couch.database import get_db

from gevent import monkey
monkey.patch_all()
from restkit.session import set_session
set_session("gevent")

POOL_SIZE = getattr(settings, 'PREINDEX_POOL_SIZE', 4)
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
        logging.error("Exception running sync, but ignoring.\n\tapp=%s\n\t%s" % (app, ex))
        return None
    print "Done with %s!!!" % app_index
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
        tries_dict = {}
        
        completed = set()
        running = []
        app_ids = set(range(len(apps)))
        for app_id in sorted(app_ids.difference(completed)):
            #keep trying all the preindexes until they all complete satisfactorily.
            print "Trying to preindex view (%d/%d) %s" % (app_id, len(apps), apps[app_id])
            curr_g = pool.spawn(do_sync, app_id)
            running.append(curr_g)

            for g in running:
                print "looping through running tasks: %s" % g
                if g.ready(): #finished execution?
                    if g.value is not None:
                        completed.add(g.value)
                        running.remove(g)
                    else:
                        print "\tSync failed for %s, trying again" % (apps[app_id])
                        curr_tries = tries_dict.get(app_id, 0)
                        if curr_tries > MAX_TRIES:
                            completed.add(app_id)
                            print "\t\tmax tries exceeded, marking as done"
                        else:
                            tries_dict[app_id] = curr_tries + 1
            print "end of main app for loop"

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





