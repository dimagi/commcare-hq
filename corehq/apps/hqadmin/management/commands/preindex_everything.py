from django.conf import settings
from django.core import cache
from django.core.mail import mail_admins
from django.core.management import call_command
from django.core.management.base import BaseCommand

import gevent

from dimagi.utils import gitinfo

from corehq.util.log import get_traceback_string

POOL_SIZE = getattr(settings, 'PREINDEX_POOL_SIZE', 8)


class Command(BaseCommand):
    help = """
    Command that syncs design docs to couch using sync_prepare_couchdb_multi and
    finds and creates new ES index mappings using ptop_preindex
    """

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
            '--mail',
            help='Mail confirmation',
            action='store_true',
            default=False,
        )
        parser.add_argument(
            '--check',
            help='Exit with 0 if preindex is complete',
            action='store_true',
            default=False,
        )

    def handle(self, num_pool, username, **options):
        email = options['mail']

        root_dir = settings.FILEPATH
        git_snapshot = gitinfo.get_project_snapshot(
            root_dir,
            submodules=False,
            log_count=1,
        )
        head = git_snapshot['commits'][0]

        if options['check']:
            exit(0 if get_preindex_complete(head) else 1)

        if get_preindex_complete(head) and email:
            mail_admins('Already preindexed', "Skipping this step")
            return
        else:
            clear_preindex_complete()

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
            call_command('sync_prepare_couchdb_multi', str(num_pool), username,
                         **{'no_mail': True})
            print("Couch preindex done")

        def pillow_preindex():
            call_command('ptop_preindex')
            print("ptop_preindex_done")

        jobs = [gevent.spawn(couch_preindex), gevent.spawn(pillow_preindex)]

        gevent.joinall(jobs)

        try:
            for job in jobs:
                job.get()
        except Exception:
            subject = " HQAdmin preindex_everything failed"
            message = get_traceback_string()
        else:
            subject = " HQAdmin preindex_everything may or may not be complete"
            message = (
                "We heard a rumor that preindex is complete,\n"
                "but it's on you to check that all tasks are complete."
            )
            set_preindex_complete(head)

        if email:
            mail_admins(subject, message)
        else:
            print('{}\n\n{}'.format(subject, message))

rcache = cache.caches['redis']
PREINDEX_COMPLETE_COMMIT = '#preindex_complete_commit'


def clear_preindex_complete():
    rcache.set(PREINDEX_COMPLETE_COMMIT, None, 86400)


def set_preindex_complete(head):
    rcache.set(PREINDEX_COMPLETE_COMMIT, head, 86400)


def get_preindex_complete(head):
    return rcache.get(PREINDEX_COMPLETE_COMMIT, None) == head
