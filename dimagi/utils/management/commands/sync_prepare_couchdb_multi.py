from django.db.models import get_apps
from django.core.management.base import BaseCommand
from couchdbkit.ext.django.loading import couchdbkit_handler
from django.core.mail import send_mail
from datetime import datetime
from dimagi.utils.couch.database import get_db
from gevent.pool import Pool
import logging
import time
from django.conf import settings

try:
    import gitinfo
    has_git = True
except ImportError:
    has_git = False


POOL_SIZE = getattr(settings, 'PREINDEX_POOL_SIZE', 4)
POOL_WAIT = getattr(settings, 'PREINDEX_POOL_WAIT', 10)

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
        print "Exception running sync, but ignoring.\n\tapp=%s\n\t%s" % (app, ex)
        return None
    return app_index

class Command(BaseCommand):
    help = 'Sync design docs to temporary ids...but multithreaded'

    def handle(self, *args, **options):
        from gevent import monkey; monkey.patch_all()
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
            g = pool.spawn(do_sync, app_id)
            if g.ready():
                if g.get() is not None:
                    completed.add(g.value)
                else:
                    print "\tSync failed for %s, trying again" % (apps[app_id])
            while len(get_db().server.active_tasks()) > num_pool:
                print "number of server active tasks exceeds pool size, waiting %d seconds..." % POOL_WAIT
                time.sleep(POOL_WAIT)

        print "All apps loaded into jobs, waiting..."
        pool.join()
        print "All apps reported complete."

        #Git info
        message = "Preindex results:\n"
        message += "\tInitiated by: %s" % username
        if has_git:
            repo = gitinfo.Repo(settings.FILEPATH)
            logs = repo.head.log()

            repo_url = repo.remote().url
            #print repo_url
            if repo_url.startswith('git://') or repo_url.startswith("https://"):
                chunks = repo_url.split("/")[-2:]
            elif repo_url.startswith("git@"):
                chunks = repo_url.split(':')[-1].split('/')
            url = "https://github.com/%s/%s/commit/%s" % (chunks[0], chunks[1].replace('.git',''), repo.head.commit.hexsha)

            message += "Commit Info:\n"
            message += "\tauthor: %s <%s>\n" % (repo.head.commit.author.name, repo.head.commit.author.email)
            message += "\tbranch: %s\n" % repo.head.ref.name
            message += "\tmessage:\n\t%s\n" % repo.head.commit.message
            message += "\tref: %s\n" % repo.head.commit.hexsha
            message += "\turl: %s\n" % url


        delta = datetime.utcnow() - start
        message += "Total time: %d seconds" % delta.seconds
        print message

        #todo: customize this more for other users
        send_mail('[commcare-hq] Preindex Complete', message, 'hq-noreply@dimagi.com', ['commcarehq-dev@dimagi.com'], fail_silently=True)





