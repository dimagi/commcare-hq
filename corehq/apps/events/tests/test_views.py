from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseFactory, CaseStructure

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import (
    CommCareUser,
    HqPermissions,
    UserRole,
    WebUser,
)
from corehq.apps.users.role_utils import UserRolePresets
from corehq.util.test_utils import flag_enabled

from ..models import ATTENDEE_CASE_TYPE, Event
from ..views import EventCreateView, EventsView


class BaseEventViewTestClass(TestCase):

    domain = 'test-domain'
    admin_web_username = 'harry_potter'
    non_admin_web_username = 'ron_weasley'
    role_web_username = 'hermione_granger'
    password = 'chamber_of_secrets'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = CaseFactory(cls.domain)
        cls.domain_obj = create_domain(cls.domain)
        cls.admin_webuser = WebUser.create(
            cls.domain,
            cls.admin_web_username,
            cls.password,
            None,
            None,
            is_admin=True,
        )
        cls.admin_webuser.save()

        cls.non_admin_webuser = WebUser.create(
            cls.domain,
            cls.non_admin_web_username,
            cls.password,
            None,
            None,
            is_admin=False,
        )
        cls.non_admin_webuser.save()

        cls.role_webuser = WebUser.create(
            cls.domain,
            cls.role_web_username,
            cls.password,
            None,
            None,
            is_admin=False,
        )
        role = cls.attendance_coordinator_role()
        cls.role_webuser.set_role(cls.domain, role.get_qualified_id())
        cls.role_webuser.save()

    @classmethod
    def tearDownClass(cls):
        cls.admin_webuser.delete(None, None)
        cls.non_admin_webuser.delete(None, None)
        cls.role_webuser.delete(None, None)
        cls.domain_obj.delete()

        user_roles = UserRole.objects.filter(
            name=UserRolePresets.ATTENDANCE_COORDINATOR, domain=cls.domain
        )
        if user_roles:
            user_roles[0].delete()

        super().tearDownClass()

    @classmethod
    def attendance_coordinator_role(cls):
        return UserRole.create(
            cls.domain,
            UserRolePresets.ATTENDANCE_COORDINATOR,
            permissions=HqPermissions(manage_attendance_tracking=True),
        )

    def log_user_in(self, user):
        self.client.login(
            username=user.username,
            password=self.password,
        )

    @property
    def endpoint(self):
        return reverse(self.urlname, args=(self.domain,))


class TestEventsListView(BaseEventViewTestClass):

    urlname = EventsView.urlname

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_user_does_not_have_permission(self):
        self.log_user_in(self.non_admin_webuser)

        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_user_is_domain_admin(self):
        self.log_user_in(self.admin_webuser)

        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200)

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_non_admin_user_with_appropriate_role(self):
        self.log_user_in(self.role_webuser)

        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200)


class TestEventsCreateView(BaseEventViewTestClass):

    urlname = EventCreateView.urlname

    @flag_enabled('ATTENDANCE_TRACKING')
    @patch.object(Event, 'save')
    def test_user_does_not_have_permission(self, event_save_method):
        self.log_user_in(self.non_admin_webuser)

        response = self.client.post(self.endpoint, self._event_data())
        self.assertEqual(response.status_code, 404)
        self.assertFalse(event_save_method.called)

    @flag_enabled('ATTENDANCE_TRACKING')
    @patch.object(Event, 'save')
    def test_user_is_domain_admin(self, event_save_method):
        self.log_user_in(self.admin_webuser)

        response = self.client.post(self.endpoint, self._event_data())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(event_save_method.called)

    @flag_enabled('ATTENDANCE_TRACKING')
    @patch.object(Event, 'save')
    def test_non_admin_user_with_appropriate_role(self, event_save_method):
        self.log_user_in(self.role_webuser)

        response = self.client.post(self.endpoint, self._event_data())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(event_save_method.called)

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_event_is_created(self):
        self.log_user_in(self.admin_webuser)
        data = self._event_data()

        mobile_worker = self._create_mobile_worker('mobileworker1')
        (attendee,) = self.factory.create_or_update_cases([CaseStructure(
            attrs={
                'owner_id': mobile_worker.user_id,
                'case_type': ATTENDEE_CASE_TYPE,
                'create': True,
            },
        )])
        data['expected_attendees'] = [attendee.case_id]

        self.client.post(self.endpoint, data)

        event = Event.objects.by_domain(self.domain).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.name, data['name'])
        self.assertEqual(event.domain, self.domain)
        self.assertEqual(event.manager_id, self.admin_webuser.user_id)

        event_attendees = event.get_expected_attendees()
        self.assertEqual(len(event_attendees), 1)
        self.assertEqual(event_attendees[0].case_id, attendee.case_id)

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_event_create_fails_with_faulty_data(self):
        self.log_user_in(self.admin_webuser)

        faulty_data = self._event_data()
        faulty_data.pop('name')

        response = self.client.post(self.endpoint, faulty_data)
        self.assertEqual(response.status_code, 200)
        error_html = (
            '<span id="error_1_id_name" class="help-block">'
            '<strong>This field is required.</strong>'
            '</span>'
        )
        self.assertIn(error_html, response.content.decode('utf-8'))

    def _event_data(self):
        timestamp = datetime.utcnow().date()

        return {
            'name': 'test-event',
            'start_date': timestamp,
            'end_date': timestamp,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
        }

    def _create_mobile_worker(self, username):
        return CommCareUser.create(
            domain=self.domain,
            username=username,
            password="*****",
            created_by=None,
            created_via=None,
        )


# class TestPaginatePossibleAttendees(BaseEventViewTestClass):
#
#     domain = "test-domain"
#     username = "testy_user"
#
#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()
#
#     @classmethod
#     def tearDownClass(cls):
#         cls.case.delete()
#         super().tearDownClass()
#
#     def test_return_domain_attendees(self):
#         url = reverse('paginated_attendees', args=[self.domain])
#         self.client.login(username=self.admin_webuser.username, password=self.password)
#
#         response = self.client.get(url, content_type="application/json;charset=utf-8")
#
#         self.assertEqual(response.status_code, 200)
#         users = json.loads(response.content)['users']
#         self.assertEqual(len(users), 1)
