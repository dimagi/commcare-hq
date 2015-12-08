from optparse import make_option
from traceback import print_stack
from dimagi.utils.couch import sync_docs
from corehq.preindex import get_preindex_plugins
from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from datetime import datetime
from gevent.pool import Pool
from django.conf import settings
setattr(settings, 'COUCHDB_TIMEOUT', 999999)


POOL_SIZE = getattr(settings, 'PREINDEX_POOL_SIZE', 8)


def do_sync(app):
    """
    Get the app for the given index.
    For multiprocessing can't pass a complex object hence the call here...again
    """

    sync_docs.sync(app.models_module, verbosity=2, temp='tmp')
    print "Preindex %s complete" % app.label


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
            self.num_pool = POOL_SIZE
        else:
            self.num_pool = int(args[0])

        if len(args) > 1:
            username = args[1]
        else:
            username = 'unknown'

        no_email = options['no_mail']

        self.handle_sync()
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

    def handle_sync(self):
        # pooling is only important when there's a serious reindex
        # (but when there is, boy is it important!)
        pool = Pool(self.num_pool)
        app_configs = [app_config for app_config in apps.get_app_configs()
                       if app_config.models_module is not None]

        for app_config in app_configs:
            print "Preindex view {}".format(app_config.label)
            pool.spawn(do_sync, app_config)

        for plugin in get_preindex_plugins():
            print "Custom preindex for plugin %s" % (
                plugin.app_label
            )
            pool.spawn(plugin.sync_design_docs, temp='tmp')

        print "All apps loaded into jobs, waiting..."
        pool.join()
        # reraise any error
        for greenlet in pool.greenlets:
            try:
                greenlet.get()
            except Exception:
                print "Error in greenlet", greenlet
                print_stack()
        print "All apps reported complete."
