from django.db.models import get_apps
from django.core.management.base import BaseCommand
from couchdbkit.ext.django.loading import couchdbkit_handler
from multiprocessing import Pool
from django.core.mail import send_mail
from datetime import datetime
import logging

try:
    import git
    has_git = True
except ImportError:
    has_git = False



def do_sync(app_index):
    """
    Get the app for the given index.
    For multiprocessing can't pass a complex object hence the call here...again
    """
    app = get_apps()[app_index]
    couchdbkit_handler.sync(app, verbosity=2, temp='tmp')
    return app_index

class Command(BaseCommand):
    help = 'Sync design docs to temporary ids...but multithreaded'

    def handle(self, *args, **options):
        start = datetime.utcnow()
        if len(args) == 0:
            num_pool = 4
        else:
            num_pool = int(args[0])

        if len(args) > 1:
            username = args[1]
        else:
            username = 'unknown'

        pool = Pool(num_pool)
        counter = 0

        apps = get_apps()
        completed = set()
        app_ids = set(range(len(apps)))
        while True:
            try:
                #keep trying all the preindexes until they all complete satisfactorily.
                print "Try to preindex views (%d/%d)..." % (len(completed), len(app_ids))
                pool_set = pool.map(do_sync, app_ids.difference(completed))
                completed.update(pool_set)
                if len(completed) == len(apps):
                    break
            except Exception, ex:
                print "Ran into an error doing preindex, restarting: %s" % ex

        #Git info
        message = "Preindex results:\n"
        if has_git:
            import settings
            repo = git.Repo(settings.filepath)
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





