from django.test import TestCase
from dimagi.utils.parsing import string_to_utc_datetime

from corehq.apps.users.models import CommCareUser, CouchUser

from pillowtop.processors.form import mark_latest_submission


class MarkLatestSubmissionTest(TestCase):

    domain = 'tracker-domain'
    username = 'tracker-user'
    password = '***'

    @classmethod
    def setUpClass(cls):
        super(MarkLatestSubmissionTest, cls).setUpClass()
        cls.user = CommCareUser.create(
            cls.domain,
            cls.username,
            cls.password
        )

    def tearDown(self):
        self.user.reporting_metadata.last_submission_date = None

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        super(MarkLatestSubmissionTest, cls).tearDownClass()

    def test_mark_latest_submission_basic(self):
        submission_date = "2017-02-05T00:00:00.000000Z"
        mark_latest_submission(self.domain, self.user._id, submission_date)
        user = CouchUser.get_by_user_id(self.user._id, self.domain)

        self.assertEqual(
            user.reporting_metadata.last_submission_date,
            string_to_utc_datetime(submission_date),
        )

    def test_mark_latest_submission_do_not_update(self):
        '''
        Ensures we do not update the user if the received_on date is after the one saved
        '''
        submission_date = "2017-02-05T00:00:00.000000Z"
        previous_date = "2017-02-04T00:00:00.000000Z"

        mark_latest_submission(self.domain, self.user._id, submission_date)
        user = CouchUser.get_by_user_id(self.user._id, self.domain)
        rev = user._rev

        mark_latest_submission(self.domain, self.user._id, previous_date)
        user = CouchUser.get_by_user_id(self.user._id, self.domain)
        new_rev = user._rev

        self.assertEqual(rev, new_rev)

    def test_mark_latest_submission_error_parsing(self):
        submission_date = "bad-date"
        mark_latest_submission(self.domain, self.user._id, submission_date)
        self.assertIsNone(self.user.reporting_metadata.last_submission_date)

        submission_date = "2017-02-05T00:00:00.000000Z"
        mark_latest_submission('bad-domain', self.user._id, submission_date)
        self.assertIsNone(self.user.reporting_metadata.last_submission_date)

        mark_latest_submission(self.domain, 'bad-user', submission_date)
        self.assertIsNone(self.user.reporting_metadata.last_submission_date)
