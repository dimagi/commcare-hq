from optparse import make_option
from datetime import datetime
from django.core.management import call_command

from django.core.management.base import BaseCommand
from django.core.mail import mail_admins
from django.conf import settings
import gevent

POOL_SIZE = getattr(settings, 'PREINDEX_POOL_SIZE', 8)


class Command(BaseCommand):
    help = 'Super preindex management command to do our bidding'

    option_list = BaseCommand.option_list + (
        make_option('--mail', help='Mail confirmation', action='store_true', default=False),
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

        email = options['mail']

        def couch_preindex():
            call_command('sync_prepare_couchdb_multi', num_pool, username, '--no-mail')
            print "Couch preindex done"

        def pillow_preindex():
            call_command('ptop_preindex')
            print "ptop_preindex_done"

        jobs = [gevent.spawn(couch_preindex), gevent.spawn(pillow_preindex)]

        gevent.joinall(jobs)

        message = "Preindex results:\n"
        message += "\tInitiated by: %s\n" % username

        delta = datetime.utcnow() - start
        message += "Total time: %d seconds" % delta.seconds
        message += "\n\nYou may now deploy"

        print message
        if email:
            mail_admins("[%s] HQAdmin preindex_everything complete" % settings.EMAIL_SUBJECT_PREFIX, message)
