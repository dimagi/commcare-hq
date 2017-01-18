from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.change_feed.topics import COMMCARE_USER, get_multi_topic_offset, \
    get_multi_topic_first_available_offsets
from corehq.apps.users.models import DomainMembership, CommCareUser

defaults = DomainMembership().to_json()
del defaults['domain']
extra_keys = ['first_name', 'last_name', 'user_data']


class Command(BaseCommand):
    args = "since_kafka_offset"
    help = "See http://manage.dimagi.com/default.asp?245969 for context"

    def add_arguments(self, parser):
        parser.add_argument('--print-kafka-offsets', action='store_true',
                            help='Just print the kafka offsets')

    def handle(self, *args, **options):
        if options['print_kafka_offsets']:
            end = get_multi_topic_offset([COMMCARE_USER])[COMMCARE_USER]
            start = get_multi_topic_first_available_offsets([COMMCARE_USER])[COMMCARE_USER]
            print "\nKakfa topic offset range: {} - {}".format(start, end)
            return

        if len(args) == 0:
            raise CommandError("Usage: python manage.py resync_location_user_data %s" % self.args)

        since = args[0]
        change_feed = KafkaChangeFeed(topics=[COMMCARE_USER], group_id='user-repair')
        for change in change_feed.iter_changes(since=since, forever=False):
            if change.deleted:
                continue

            user = change.get_document()
            if user_looks_ok(user):
                continue

            restore_domain_membership(user)


def user_looks_ok(user):
    if 'commcare_project' not in user.user_data:
        return True

    domain_membership = user.domain_membership
    if any(key in domain_membership for key in extra_keys):
        # membership has not been reset
        return True

    for key, default_value in defaults.items():
        if domain_membership[key] != default_value:
            # domain membership has been updated
            return True

    return False


def restore_domain_membership(user):
    doc_id = user._id
    db = CommCareUser.get_db()
    revisions = get_doc_revisions(db, doc_id)
    for rev in revisions[1:]:
        doc = get_doc_rev(db, doc_id, rev)
        prev_user = CommCareUser.wrap(doc)
        if user_looks_ok(prev_user):
            prev_domain_membership = prev_user.domain_membership
            user.domain_membership = prev_domain_membership
            user.save()
            return


def get_doc_revisions(db, doc_id):
    res = db.get(doc_id, revs=True)
    start = res['_revisions']['start']
    ids = res['_revisions']['ids']
    return ["{}-{}".format(start-i, rev) for i, rev in enumerate(ids)]


def get_doc_rev(db, doc_id, rev):
    try:
        return db.get(doc_id, rev=rev)
    except ResourceNotFound:
        return None
