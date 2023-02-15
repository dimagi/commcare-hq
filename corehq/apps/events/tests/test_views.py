from django.test import TestCase
from django.urls import reverse
from datetime import datetime
from unittest.mock import patch

from corehq.apps.events.models import Event, get_domain_events
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.events.views import EventsView, EventCreateView
from corehq.apps.users.models import WebUser, HqPermissions
from corehq.util.test_utils import flag_enabled
from corehq.apps.users.models import UserRole
from corehq.apps.users.role_utils import UserRolePresets
from corehq.form_processor.models import CommCareCase


class BaseEventViewTestClass(TestCase):

    domain = 'test-domain'
    admin_web_username = 'harry_potter'
    non_admin_web_username = 'ron_weasley'
    role_web_username = 'hermione_granger'
    password = 'chamber_of_secrets'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
    def test_event_case_is_created(self):
        self.log_user_in(self.admin_webuser)

        data = self._event_data()
        self.client.post(self.endpoint, data)

        events = get_domain_events(self.domain)
        case_id = events[0].event_id
        case_ = CommCareCase.objects.get_case(case_id, self.domain)

        self.assertEqual(case_.name, data['name'])
        self.assertEqual(case_.domain, self.domain)
        self.assertEqual(case_.owner_id, self.admin_webuser.user_id)
        self.assertEqual(
            case_.get_case_property('attendance_target'),
            str(data['attendance_target'])
        )
        self.assertEqual(
            case_.get_case_property('is_open'),
            str(Event.is_open),
        )
        self.assertEqual(
            case_.get_case_property('attendee_list_status'),
            str(Event.attendee_list_status),
        )

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_event_case_create_fails_with_faulty_data(self):
        self.log_user_in(self.admin_webuser)

        faulty_data = self._event_data()
        faulty_data.pop('name')

        response = self.client.post(self.endpoint, faulty_data)
        self.assertEqual(response.status_code, 400)

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
