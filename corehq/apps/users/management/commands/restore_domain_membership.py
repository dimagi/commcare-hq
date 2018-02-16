from __future__ import print_function
from __future__ import absolute_import
import json

from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.change_feed.topics import COMMCARE_USER, get_multi_topic_offset, \
    get_multi_topic_first_available_offsets
from corehq.apps.users.models import DomainMembership, CommCareUser
from corehq.util.decorators import change_log_level
from six.moves import input

defaults = DomainMembership().to_json()
del defaults['domain']
extra_keys = ['first_name', 'last_name', 'user_data']


class Command(BaseCommand):
    help = "See http://manage.dimagi.com/default.asp?245969 for context"

    def add_arguments(self, parser):
        parser.add_argument(
            '--offset-start', type=int, default=-1,
            help='Kafka offset to start from. Defaults to first available offset')
        parser.add_argument(
            '--offset-end', type=int, default=-1,
            help='Kafka offset to stop at. Defaults to last available offset')
        parser.add_argument('--check', action='store_true',
                            help='Confirm before making any changes to users.')

        parser.add_argument('--print-kafka-offsets', action='store_true',
                            help='Just print the kafka offsets')

        parser.add_argument('--find-start-offset', action='store_true',
                            help='Find the offset to start from')

    @change_log_level('kafka', 'ERROR')
    def handle(self, **options):
        if options['print_kafka_offsets']:
            start, end = self.get_min_max_offsets()
            print("\n\nKakfa topic offset range: {} - {}".format(start, end))
            return

        start_offset = options['offset_start']
        end_offset = options['offset_end']

        start, end = self.get_min_max_offsets()
        if start_offset < start:
            start_offset = start
        if end_offset < 0 or end_offset > end:
            end_offset = end

        if start_offset > end_offset:
            raise CommandError("Start greater than end: {} > {}".format(start_offset, end_offset))

        print('Using kafka offset range: {} - {}'.format(start_offset, end_offset))

        if options['find_start_offset']:
            find_first_match = FindFirstMatch(start_offset, end_offset, check_user_at_offset)
            first_matching_offset = find_first_match.search()
            if first_matching_offset is None:
                raise CommandError("Unable to find first matching offset. "
                                   "Try a different search range.")
            else:
                print("\nFirst matching offset = {}".format(first_matching_offset))
            return

        check = options['check']

        seen_ids = set()
        change_feed = KafkaChangeFeed(topics=[COMMCARE_USER], group_id='user-repair')
        for change in change_feed.iter_changes(since=start_offset, forever=False):
            if change.sequence_id > end_offset:
                return

            if change.id in seen_ids:
                continue

            seen_ids.add(change.id)

            if change.deleted:
                continue

            try:
                user = change.get_document()
            except ResourceNotFound:
                continue

            user = CommCareUser.wrap(user)

            if user_looks_ok(user):
                continue

            restore_domain_membership(user, check=check)

            if change.sequence_id % 100 == 0:
                print("Processed up to offset: {}".format(change.sequence_id))

    def get_min_max_offsets(self):
        end = get_multi_topic_offset([COMMCARE_USER])[COMMCARE_USER]
        start = get_multi_topic_first_available_offsets([COMMCARE_USER])[COMMCARE_USER]
        return start, {partition: offset - 1 for partition, offset in end.items()}  # end is next available offset


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


def restore_domain_membership(user, check=False):
    doc_id = user._id
    db = CommCareUser.get_db()
    revisions = get_doc_revisions(db, doc_id)
    for rev in revisions[1:]:
        doc = get_doc_rev(db, doc_id, rev)
        if not doc:
            continue
        prev_user = CommCareUser.wrap(doc)
        if user_looks_ok(prev_user):
            if user.location_id != prev_user.domain_membership.location_id:
                continue

            if user.assigned_location_ids != prev_user.domain_membership.assigned_location_ids:
                continue

            if check:
                print('Ready to patch user: {} ({})'.format(user.domain, doc_id))
                old = json.dumps(user.domain_membership.to_json(), indent=2)
                print('Old domain membership: \n{}\n'.format(old))
                new = json.dumps(prev_user.domain_membership.to_json(), indent=2)
                print('New domain membership: \n{}\n'.format(new))
                if not confirm('Proceed with updating user?'):
                    return

            print("Patching user: {} ({})".format(user.domain, doc_id))
            prev_domain_membership = prev_user.domain_membership
            user.domain_membership = prev_domain_membership
            user.save()
            return

    print('Unable to fix user: {} ({})'.format(user.domain, doc_id))


def get_doc_revisions(db, doc_id):
    res = db.get(doc_id, revs=True)
    start = res['_revisions']['start']
    ids = res['_revisions']['ids']
    return ["{}-{}".format(start - i, rev) for i, rev in enumerate(ids)]


def get_doc_rev(db, doc_id, rev):
    try:
        return db.get(doc_id, rev=rev)
    except ResourceNotFound:
        return None


def check_user_at_offset(offset):
    change_feed = KafkaChangeFeed(topics=[COMMCARE_USER], group_id='user-repair')
    change = None
    try:
        change = next(change_feed.iter_changes(since=offset, forever=False))
    except StopIteration:
        pass

    if not change:
        raise CommandError("No change at offset: {}".format(offset))

    if change.deleted:
        return False

    try:
        user = change.get_document()
    except ResourceNotFound:
        return False

    return 'commcare_project' in user['user_data']


class FindFirstMatch(object):
    """
    Helper class to find the first match in a stream of items.

    Assumes that the stream is continuous from ``min_index`` to ``max_index`` and that
    the a match at any index indicates that all further indices will also match.

    :param min_index: Numeric index of the first event
    :param max_index: Numeric index of the last event
    :param match_at_index: Function that takes in an index and returns True
                              if the item for the index matches.
    """
    def __init__(self, min_index, max_index, match_at_index):
        self.min = min_index
        self.max = max_index
        self.match_at_index = match_at_index

        self._min_matching_index = None

    def _match_at_index(self, index):
        if self.match_at_index(index):
            if self._min_matching_index is None or index < self._min_matching_index:
                self._min_matching_index = index
            return True
        return False

    def search(self):
        if self.match_at_index(self.min):
            return self.min
        if not self.match_at_index(self.max):
            return

        min_index = self.min + 1  # since we've already checked min
        max_index = self.max - 1  # since we've already checked max
        while max_index >= min_index:
            midpoint = (min_index + max_index) // 2
            if self._match_at_index(midpoint):
                max_index = midpoint - 1  # search down
            else:
                min_index = midpoint + 1  # search up

        return self._min_matching_index


def confirm(msg):
    return input(msg + "\n(y/n)") == 'y'
