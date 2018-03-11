from __future__ import absolute_import
import datetime

from django.test import TestCase

from casexml.apps.case.tests.util import delete_all_sync_logs
from casexml.apps.phone.models import SyncLog, SyncLogSQL, properly_wrap_sync_log
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser, LastSync
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.change_feed.tests.utils import get_test_kafka_consumer


class SyncLogPillowTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(SyncLogPillowTest, cls).setUpClass()

        DOMAIN = "synclog_test"
        cls.domain = Domain(name=DOMAIN)
        cls.domain.save()

        cls.ccuser = CommCareUser(
            domain=DOMAIN,
            username='ccuser',
            last_login=datetime.datetime.now(),
            date_joined=datetime.datetime.now(),
        )
        cls.ccuser.save()

    @classmethod
    def tearDownClass(cls):
        delete_all_sync_logs()
        cls.ccuser.delete()
        cls.domain.delete()
        super(SyncLogPillowTest, cls).tearDownClass()

    def _get_latest_synclog(self):
        return properly_wrap_sync_log(SyncLogSQL.objects.order_by('date').last().doc)

    def test_pillow(self):
        from corehq.apps.change_feed.topics import get_topic_offset
        from corehq.pillows.synclog import get_user_sync_history_pillow
        consumer = get_test_kafka_consumer(topics.SYNCLOG_SQL)
        # get the seq id before the change is published
        kafka_seq = get_topic_offset(topics.SYNCLOG_SQL)

        # make sure user has empty reporting-metadata before a sync
        self.assertEqual(self.ccuser.reporting_metadata.last_syncs, [])

        # do a sync
        synclog = SyncLog(domain=self.domain.name, user_id=self.ccuser._id,
                          date=datetime.datetime(2015, 7, 1, 0, 0))
        synclog.save()

        # make sure kafka change updates the user with latest sync info
        message = next(consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        synclog = self._get_latest_synclog()
        self.assertEqual(change_meta.document_id, synclog._id)
        self.assertEqual(change_meta.domain, self.domain.name)

        # make sure processor updates the user correctly
        pillow = get_user_sync_history_pillow()
        pillow.process_changes(since=kafka_seq, forever=False)
        ccuser = CommCareUser.get(self.ccuser._id)
        self.assertEqual(len(ccuser.reporting_metadata.last_syncs), 1)
        self.assertEqual(ccuser.reporting_metadata.last_syncs[0].sync_date, synclog.date)
        self.assertEqual(ccuser.reporting_metadata.last_sync_for_user.sync_date, synclog.date)
