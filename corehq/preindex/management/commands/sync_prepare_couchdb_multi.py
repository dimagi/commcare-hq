from optparse import make_option
from traceback import print_stack
from corehq.preindex import get_preindex_plugins
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from datetime import datetime
from gevent.pool import Pool
from django.conf import settings
from corehq.preindex.accessors import sync_design_doc, get_preindex_designs

setattr(settings, 'COUCHDB_TIMEOUT', 999999)


POOL_SIZE = getattr(settings, 'PREINDEX_POOL_SIZE', 8)


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
        for design in get_preindex_designs():
            pool.spawn(sync_design_doc, design, temp='tmp')

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
