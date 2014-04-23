from optparse import make_option
from django.core.management import call_command

from django.core.management.base import BaseCommand
from django.core.mail import mail_admins
from django.conf import settings
from dimagi.utils import gitinfo
import gevent

POOL_SIZE = getattr(settings, 'PREINDEX_POOL_SIZE', 8)


class Command(BaseCommand):
    help = 'Super preindex management command to do our bidding'

    option_list = BaseCommand.option_list + (
        make_option('--mail', help='Mail confirmation', action='store_true',
                    default=False),
    )

    def handle(self, *args, **options):
        if len(args) == 0:
            num_pool = POOL_SIZE
        else:
            num_pool = int(args[0])

        if len(args) > 1:
            username = args[1]
        else:
            username = 'unknown'

        email = options['mail']

        root_dir = settings.FILEPATH
        git_snapshot = gitinfo.get_project_snapshot(
            root_dir,
            submodules=False,
            log_count=1,
        )
        head = git_snapshot['commits'][0]

        commit_info = "\nCommit Info:\nOn Branch %s, SHA: %s" % (
            git_snapshot['current_branch'], head['sha'])

        pre_message = list()
        pre_message.append("Heads up, %s has started preindexing" % username)
        pre_message.append(commit_info)

        if email:
            mail_admins(
                " HQAdmin preindex_everything started", '\n'.join(pre_message)
            )

        def couch_preindex():
            call_command('sync_prepare_couchdb_multi', num_pool, username,
                         **{'no_mail': True})
            print "Couch preindex done"

        def pillow_preindex():
            call_command('ptop_preindex')
            print "ptop_preindex_done"

        jobs = [gevent.spawn(couch_preindex), gevent.spawn(pillow_preindex)]

        gevent.joinall(jobs)

        message = '\n'.join([
            "We heard a rumor that preindex is complete, "
            "but it's on you to check that all tasks are complete."
        ])

        if email:
            mail_admins(
                " HQAdmin preindex_everything may or may not be complete",
                message
            )
        else:
            print message
