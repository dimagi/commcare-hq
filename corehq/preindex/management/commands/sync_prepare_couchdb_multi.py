from optparse import make_option
from dimagi.utils.couch import sync_docs
from gevent import monkey
from corehq.preindex import get_preindex_plugins

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


POOL_SIZE = getattr(settings, 'PREINDEX_POOL_SIZE', 8)
POOL_WAIT = getattr(settings, 'PREINDEX_POOL_WAIT', 10)
MAX_TRIES = getattr(settings, 'PREINDEX_MAX_TRIES', 3)


def do_sync(app_index):
    """
    Get the app for the given index.
    For multiprocessing can't pass a complex object hence the call here...again
    """
    #sanity check:
    app = get_apps()[app_index]
    sync_docs.sync(app, verbosity=2, temp='tmp')
    print "preindex %s complete" % app_index
    return app_index


class Command(BaseCommand):
    help = 'Sync design docs to temporary ids...but multithreaded'

    option_list = BaseCommand.option_list + (
        make_option(
            '--no-mail',
            help="Don't send email confirmation",
            action='store_true',
            default=False,
        ),
    )

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

        no_email = options['no_mail']

        pool = Pool(num_pool)

        apps = get_apps()

        completed = set()
        app_ids = set(range(len(apps)))
        for app_id in sorted(app_ids.difference(completed)):
            # keep trying all the preindexes
            # until they all complete satisfactorily.
            print "Trying to preindex view (%d/%d) %s" % (
                app_id, len(apps), apps[app_id])
            pool.spawn(do_sync, app_id)

        for plugin in get_preindex_plugins():
            print "Custom preindex for plugin %s" % (
                plugin.app_label
            )
            pool.spawn(plugin.sync_design_docs, temp='tmp')

        print "All apps loaded into jobs, waiting..."
        pool.join()
        # reraise any error
        for greenlet in pool.greenlets:
            greenlet.get()
        print "All apps reported complete."

        message = "Preindex results:\n"
        message += "\tInitiated by: %s\n" % username

        delta = datetime.utcnow() - start
        message += "Total time: %d seconds" % delta.seconds

        if not no_email:
            print message
            send_mail(
                '%s CouchDB Preindex Complete' % settings.EMAIL_SUBJECT_PREFIX,
                message,
                settings.SERVER_EMAIL,
                [x[1] for x in settings.ADMINS],
                fail_silently=True,
            )
