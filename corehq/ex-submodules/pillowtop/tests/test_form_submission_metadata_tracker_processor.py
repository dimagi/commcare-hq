from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from dimagi.utils.parsing import string_to_utc_datetime

from corehq.apps.users.models import CommCareUser, CouchUser

from pillowtop.processors.form import mark_latest_submission


class MarkLatestSubmissionTest(TestCase):

    domain = 'tracker-domain'
    username = 'tracker-user'
    password = '***'
    app_id = 'app-id'
    build_id = 'build-id'
    version = '2'
    metadata = {
        'deviceID': 'device-id'
    }

    @classmethod
    def setUpClass(cls):
        super(MarkLatestSubmissionTest, cls).setUpClass()
        cls.user = CommCareUser.create(
            cls.domain,
            cls.username,
            cls.password
        )

    def tearDown(self):
        user = CouchUser.get_by_user_id(self.user._id, self.domain)
        user.reporting_metadata.last_submissions = []
        user.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        super(MarkLatestSubmissionTest, cls).tearDownClass()

    def test_mark_latest_submission_basic(self):
        submission_date = "2017-02-05T00:00:00.000000Z"
        mark_latest_submission(
            self.domain,
            self.user._id,
            self.app_id,
            self.build_id,
            self.version,
            self.metadata,
            submission_date,
        )
        user = CouchUser.get_by_user_id(self.user._id, self.domain)

        self.assertEqual(len(user.reporting_metadata.last_submissions), 1)
        last_submission = user.reporting_metadata.last_submissions[0]

        self.assertEqual(
            last_submission.submission_date,
            string_to_utc_datetime(submission_date),
        )
        self.assertEqual(
            last_submission.app_id,
            self.app_id,
        )
        self.assertEqual(
            last_submission.build_id,
            self.build_id,
        )
        self.assertEqual(
            last_submission.device_id,
            self.metadata['deviceID'],
        )
        self.assertEqual(last_submission.build_version, 2)

    def test_mark_latest_submission_do_not_update(self):
        '''
        Ensures we do not update the user if the received_on date is after the one saved
        '''
        submission_date = "2017-02-05T00:00:00.000000Z"
        previous_date = "2017-02-04T00:00:00.000000Z"

        mark_latest_submission(
            self.domain,
            self.user._id,
            self.app_id,
            self.build_id,
            self.version,
            self.metadata,
            submission_date,
        )
        user = CouchUser.get_by_user_id(self.user._id, self.domain)
        rev = user._rev

        mark_latest_submission(
            self.domain,
            self.user._id,
            self.app_id,
            self.build_id,
            self.version,
            self.metadata,
            previous_date,
        )
        user = CouchUser.get_by_user_id(self.user._id, self.domain)
        new_rev = user._rev

        self.assertEqual(len(user.reporting_metadata.last_submissions), 1)
        self.assertEqual(rev, new_rev)

    def test_mark_latest_submission_error_parsing(self):
        submission_date = "bad-date"
        mark_latest_submission(
            self.domain,
            self.user._id,
            self.app_id,
            self.build_id,
            self.version,
            self.metadata,
            submission_date,
        )
        self.assertListEqual(self.user.reporting_metadata.last_submissions, [])

        submission_date = "2017-02-05T00:00:00.000000Z"
        mark_latest_submission(
            'bad-domain',
            self.user._id,
            self.app_id,
            self.build_id,
            self.version,
            self.metadata,
            submission_date,
        )
        self.assertListEqual(self.user.reporting_metadata.last_submissions, [])

        mark_latest_submission(
            self.domain,
            'bad-user',
            self.app_id,
            self.build_id,
            self.version,
            self.metadata,
            submission_date,
        )
        self.assertListEqual(self.user.reporting_metadata.last_submissions, [])

    def test_mark_latest_submission_multiple(self):
        submission_date = "2017-02-05T00:00:00.000000Z"
        mark_latest_submission(
            self.domain,
            self.user._id,
            self.app_id,
            self.build_id,
            self.version,
            self.metadata,
            submission_date,
        )
        mark_latest_submission(
            self.domain,
            self.user._id,
            'other-app-id',
            self.build_id,
            self.version,
            self.metadata,
            submission_date,
        )
        user = CouchUser.get_by_user_id(self.user._id, self.domain)
        self.assertEqual(len(user.reporting_metadata.last_submissions), 2)
