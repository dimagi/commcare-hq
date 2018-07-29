from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from traceback import print_stack
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

    def add_arguments(self, parser):
        parser.add_argument(
            'num_pool',
            default=POOL_SIZE,
            nargs='?',
            type=int,
        )
        parser.add_argument(
            'username',
            default='unknown',
            nargs='?',
        )
        parser.add_argument(
            '--no-mail',
            help="Don't send email confirmation",
            action='store_true',
            default=False,
        )

    def handle(self, num_pool, username, **options):
        start = datetime.utcnow()
        self.num_pool = num_pool
        no_email = options['no_mail']

        self.handle_sync()
        message = "Preindex results:\n"
        message += "\tInitiated by: %s\n" % username

        delta = datetime.utcnow() - start
        message += "Total time: %d seconds" % delta.seconds

        if not no_email:
            print(message)
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

        print("All apps loaded into jobs, waiting...")
        pool.join()
        # reraise any error
        for greenlet in pool.greenlets:
            try:
                greenlet.get()
            except Exception:
                print("Error in greenlet", greenlet)
                print_stack()
        print("All apps reported complete.")
