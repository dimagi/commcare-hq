import pytz
import uuid

from datetime import datetime
from django.test import SimpleTestCase
from dimagi.utils.dates import DateSpan

from corehq.util.elastic import delete_es_index
from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group
from corehq.form_processor.tests.utils import TestFormMetadata
from corehq.pillows.xform import XFormPillow
from corehq.pillows.user import UserPillow
from corehq.pillows.group import GroupPillow
from corehq.apps.reports.analytics.esaccessors import (
    get_submission_counts_by_user,
    get_completed_counts_by_user,
    get_submission_counts_by_date,
    get_user_stubs,
    get_group_stubs,
)
from corehq.util.test_utils import make_es_ready_form


class BaseESAccessorsTest(SimpleTestCase):

    def setUp(self):
        self.domain = 'esdomain'
        self.pillow = self.pillow_class()

    def tearDown(self):
        delete_es_index(self.pillow.es_index)


class TestFormESAccessors(BaseESAccessorsTest):

    pillow_class = XFormPillow

    def _send_form_to_es(self, domain=None, completion_time=None, received_on=None):
        metadata = TestFormMetadata(
            domain=domain or self.domain,
            time_end=completion_time or datetime.utcnow(),
            received_on=received_on or datetime.utcnow(),
        )
        form_pair = make_es_ready_form(metadata)
        self.pillow.change_transport(form_pair.json_form)
        self.pillow.get_es_new().indices.refresh(self.pillow.es_index)
        return form_pair

    def test_basic_completed_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(completion_time=datetime(2013, 7, 2))

        results = get_completed_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    def test_completed_out_of_range_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(completion_time=datetime(2013, 8, 2))
        self._send_form_to_es(completion_time=datetime(2013, 7, 2))

        results = get_completed_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    def test_completed_different_domain_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(completion_time=datetime(2013, 7, 3), domain='not-in-my-backyard')
        self._send_form_to_es(completion_time=datetime(2013, 7, 2))

        results = get_completed_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    def test_basic_submission_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15)

        self._send_form_to_es(received_on=received_on)

        results = get_submission_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    def test_submission_out_of_range_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(received_on=datetime(2013, 8, 15))

        self._send_form_to_es(received_on=datetime(2013, 7, 15))

        results = get_submission_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    def test_submission_different_domain_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15)

        self._send_form_to_es(received_on=received_on)
        self._send_form_to_es(received_on=received_on, domain='not-in-my-backyard')

        results = get_submission_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    def test_basic_submission_by_date(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15)

        self._send_form_to_es(received_on=received_on)

        results = get_submission_counts_by_date(
            self.domain,
            ['cruella_deville'],
            DateSpan(start, end),
            pytz.utc
        )
        self.assertEquals(results['2013-07-15'], 1)

    def test_timezone_differences(self):
        """
        Our received_on dates are always in UTC, so if we submit a form right at midnight UTC, then the report
        should show that form being submitted the day before if viewing from an earlier timezone like New York
        """
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15, 0, 0, 0)
        timezone = pytz.timezone('America/New_York')

        self._send_form_to_es(received_on=received_on)

        results = get_submission_counts_by_date(
            self.domain,
            ['cruella_deville'],
            DateSpan(start, end),
            timezone
        )
        self.assertEquals(results['2013-07-14'], 1)


class TestUserESAccessors(BaseESAccessorsTest):

    pillow_class = UserPillow

    def setUp(self):
        super(TestUserESAccessors, self).setUp()
        self.username = 'superman'
        self.first_name = 'clark'
        self.last_name = 'kent'
        self.doc_type = 'CommCareUser'

    def _send_user_to_es(self, _id=None, is_active=True):
        user = CommCareUser(
            domain=self.domain,
            username=self.username,
            _id=_id or uuid.uuid4().hex,
            is_active=is_active,
            first_name=self.first_name,
            last_name=self.last_name,
        )
        self.pillow.change_transport(user.to_json())
        self.pillow.get_es_new().indices.refresh(self.pillow.es_index)
        return user

    def test_active_user_query(self):
        self._send_user_to_es('123')
        results = get_user_stubs(['123'])

        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], {
            '_id': '123',
            'username': self.username,
            'is_active': True,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'doc_type': self.doc_type,
        })

    def test_inactive_user_query(self):
        self._send_user_to_es('123', is_active=False)
        results = get_user_stubs(['123'])

        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], {
            '_id': '123',
            'username': self.username,
            'is_active': False,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'doc_type': self.doc_type,
        })


class TestGroupESAccessors(BaseESAccessorsTest):

    pillow_class = GroupPillow

    def setUp(self):
        super(TestGroupESAccessors, self).setUp()
        self.group_name = 'justice league'
        self.reporting = True
        self.case_sharing = False

    def _send_group_to_es(self, _id=None):
        group = Group(
            domain=self.domain,
            name=self.group_name,
            case_sharing=self.case_sharing,
            reporting=self.reporting,
            _id=_id or uuid.uuid4().hex,
        )
        self.pillow.change_transport(group.to_json())
        self.pillow.get_es_new().indices.refresh(self.pillow.es_index)
        return group

    def test_group_query(self):
        self._send_group_to_es('123')
        results = get_group_stubs(['123'])

        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], {
            '_id': '123',
            'name': self.group_name,
            'case_sharing': self.case_sharing,
            'reporting': self.reporting,
        })
