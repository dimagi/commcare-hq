from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch
from flaky import flaky
import uuid

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseFactory, CaseStructure

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.apps.users.role_utils import UserRolePresets
from corehq.form_processor.models import CommCareCase
from corehq.util.test_utils import flag_enabled
from corehq.apps.events.models import AttendanceTrackingConfig
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.case_search import case_search_adapter
from corehq.form_processor.tests.utils import create_case
from corehq.apps.es.users import user_adapter

from ..models import (
    Event,
    get_attendee_case_type,
    AttendeeModel,
    LOCATION_IDS_CASE_PROPERTY,
)
from ..views import (
    EventCreateView,
    EventsView,
    AttendeesConfigView,
    ConvertMobileWorkerAttendeesView,
    AttendeeDeleteView,
    EventEditView
)
from corehq.apps.users.models import CommCareUser


@es_test(requires=[user_adapter], setup_class=True)
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
        cls.mobile_worker = CommCareUser.create(
            cls.domain, "UserX", "123", None, None, email="user_x@email.com"
        )
        user_adapter.index(cls.mobile_worker, refresh=True)

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


@flag_enabled('ATTENDANCE_TRACKING')
class TestEventsEditView(BaseEventViewTestClass):

    urlname = EventEditView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        today = datetime.utcnow()
        cls.event = Event(
            domain=cls.domain,
            name='test-event',
            start_date=today,
            end_date=today,
            attendance_target=10
        )
        cls.event.save()

    @classmethod
    def tearDownClass(cls):
        cls.event.delete()
        super().tearDownClass()

    def _get_response(self, event_id=None):
        if not event_id:
            event_id = uuid.uuid4()
        endpoint = reverse(self.urlname, args=(self.domain, event_id))
        response = self.client.get(endpoint)
        return response

    def test_user_does_not_have_permission(self):
        self.log_user_in(self.non_admin_webuser)
        response = self._get_response(self.event.event_id)
        self.assertEqual(response.status_code, 404)

    def test_user_is_domain_admin(self):
        self.log_user_in(self.admin_webuser)
        response = self._get_response(self.event.event_id)
        self.assertEqual(response.status_code, 200)

    def test_non_admin_user_with_appropriate_role(self):
        self.log_user_in(self.role_webuser)
        response = self._get_response(self.event.event_id)
        self.assertEqual(response.status_code, 200)

    def test_event_not_found(self):
        self.log_user_in(self.admin_webuser)
        response = self._get_response()
        self.assertEqual(response.status_code, 404)


class TestEventsCreateView(BaseEventViewTestClass):

    urlname = EventCreateView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = CaseFactory(cls.domain)

    @contextmanager
    def _get_attendee(self):
        case_type = get_attendee_case_type(self.domain)
        (attendee,) = self.factory.create_or_update_cases([
            CaseStructure(attrs={
                'case_type': case_type,
                'create': True,
            })
        ])
        try:
            yield attendee
        finally:
            CommCareCase.objects.hard_delete_cases(
                self.domain,
                [attendee.case_id],
            )

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
        with self._get_attendee() as attendee_case:
            data = self._event_data()
            data['expected_attendees'] = [attendee_case.case_id]

            self.client.post(self.endpoint, data)

            event = Event.objects.by_domain(self.domain).first()

            self.assertEqual(event.name, data['name'])
            self.assertEqual(event.domain, self.domain)
            self.assertEqual(event.manager_id, self.admin_webuser.user_id)

            expected_attendees = event.get_expected_attendees()
            self.assertEqual(len(expected_attendees), 1)
            self.assertEqual(
                expected_attendees[0].case_id,
                attendee_case.case_id,
            )

    @flaky
    @flag_enabled('ATTENDANCE_TRACKING')
    def test_event_create_fails_with_faulty_data(self):
        self.log_user_in(self.admin_webuser)

        faulty_data = self._event_data()
        faulty_data.pop('name')

        response = self.client.post(self.endpoint, faulty_data)
        self.assertEqual(response.status_code, 200)

        response_body = response.content.decode('utf-8')
        self.assertIn('error_1_id_name', response_body)
        self.assertIn('This field is required', response_body)

    def _event_data(self):
        timestamp = datetime.utcnow().date()
        return {
            'name': 'test-event',
            'start_date': timestamp,
            'end_date': timestamp,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
            'attendance_takers': [self.mobile_worker.user_id],
        }


class TestAttendeesConfigView(BaseEventViewTestClass):
    urlname = AttendeesConfigView.urlname

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_get_for_non_existent_attendance_tracking_config(self):
        self.log_user_in(self.role_webuser)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data['mobile_worker_attendee_enabled'], False)


class TestConvertMobileWorkerAttendeesView(BaseEventViewTestClass):
    urlname = ConvertMobileWorkerAttendeesView.urlname

    @flag_enabled('ATTENDANCE_TRACKING')
    @patch('corehq.apps.events.tasks.sync_mobile_worker_attendees')
    def test_toggle_updates_attendance_tracking_config(self, sync_mobile_worker_attendees_mock):
        config, _created = AttendanceTrackingConfig.objects.get_or_create(domain=self.domain)
        update_value = not config.mobile_worker_attendees
        self.log_user_in(self.role_webuser)

        response = self.client.get(self.endpoint, content_type='application/json')
        self.assertEqual(response.status_code, 302)

        # Make sure it updated
        config, _created = AttendanceTrackingConfig.objects.get_or_create(domain=self.domain)
        self.assertEqual(config.mobile_worker_attendees, update_value)

    @flag_enabled('ATTENDANCE_TRACKING')
    @patch('corehq.apps.events.views.sync_mobile_worker_attendees.delay')
    @patch('soil.CachedDownload.set_task')
    def test_enable_mobile_worker_attendee_triggers_task(self, sync_mobile_worker_attendees_mock, *args):
        config, _created = AttendanceTrackingConfig.objects.get_or_create(domain=self.domain)
        self.log_user_in(self.role_webuser)

        # Make sure we respond with the correct value
        self.assertFalse(config.mobile_worker_attendees)

        response = self.client.get(self.endpoint, content_type='application/json')
        self.assertEqual(response.status_code, 302)
        sync_mobile_worker_attendees_mock.assert_called_once()

    @flag_enabled('ATTENDANCE_TRACKING')
    @patch('corehq.apps.events.views.close_mobile_worker_attendee_cases.delay')
    @patch('soil.CachedDownload.set_task')
    def test_disable_mobile_worker_attendee_triggers_task(self, close_mobile_worker_attendee_cases_mock, *args):
        config, _created = AttendanceTrackingConfig.objects.get_or_create(domain=self.domain)
        self.log_user_in(self.role_webuser)

        # Make sure we respond with the correct value
        self.assertFalse(config.mobile_worker_attendees)

        response = self.client.get(self.endpoint, content_type='application/json')
        self.assertEqual(response.status_code, 302)
        close_mobile_worker_attendee_cases_mock.assert_called_once()


class TestAttendeesDeleteView(BaseEventViewTestClass):

    urlname = AttendeeDeleteView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = CaseFactory(cls.domain)

    @contextmanager
    def _get_attendee_case(self):
        case_type = get_attendee_case_type(self.domain)
        (attendee,) = self.factory.create_or_update_cases([
            CaseStructure(attrs={
                'case_type': case_type,
                'create': True,
            })
        ])
        try:
            yield attendee
        finally:
            CommCareCase.objects.hard_delete_cases(
                self.domain,
                [attendee.case_id],
            )

    def _delete_attendee(self, attendee_id):
        endpoint = reverse(self.urlname, args=(self.domain, attendee_id))
        data = {
            'domain': self.domain,
            'attendee_id': attendee_id
        }
        return self.client.post(endpoint, data)

    @flag_enabled('ATTENDANCE_TRACKING')
    @patch.object(AttendeeModel, 'delete')
    def test_user_does_not_have_permission(self, attendee_delete_method):
        self.log_user_in(self.non_admin_webuser)
        with self._get_attendee_case() as case:
            attendee = AttendeeModel(case=case, domain=self.domain)
            attendee.save()

        response = self._delete_attendee(attendee.case_id)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(attendee_delete_method.called)

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_attendee_is_deleted(self):
        self.log_user_in(self.admin_webuser)
        with self._get_attendee_case() as case:
            attendee = AttendeeModel(case=case, domain=self.domain)
            attendee.save()

            response = self._delete_attendee(attendee.case_id)
            self.assertEqual(response.status_code, 302)
            attendee_case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(attendee_case.get_case_property('closed'))

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_cannot_delete_tracked_attendee(self):
        today = datetime.utcnow().date()
        event = Event(
            domain=self.domain,
            name='test-event',
            start_date=today,
            end_date=today,
            attendance_target=10,
            sameday_reg=True,
            track_each_day=False,
            manager_id=self.admin_webuser.user_id
        )
        event.save()

        self.log_user_in(self.admin_webuser)
        with self._get_attendee_case() as case:
            attendee = AttendeeModel(case=case, domain=self.domain)
            attendee.save()
            event.mark_attendance([case], datetime.now())

            response = self._delete_attendee(attendee.case_id)
            self.assertEqual(response.status_code, 400)
            attendee_case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(attendee_case.get_case_property('closed'))
            self.assertEqual(
                response.content.decode('utf-8'),
                '{"failed": "Cannot delete an attendee that has been tracked in one or more events."}'
            )


@es_test(requires=[case_search_adapter], setup_class=True)
class TestGetAttendeesAndAttendanceTakersView(BaseEventViewTestClass):

    urlname = 'get_attendees_and_attendance_takers'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        location_type = LocationType.objects.create(
            domain=cls.domain,
            name='Place'
        )
        cls.locations = [
            SQLLocation.objects.create(
                domain=cls.domain,
                name='Mordor',
                location_id=str(uuid.uuid4().hex),
                location_type=location_type
            ),
            SQLLocation.objects.create(
                domain=cls.domain,
                name='Shire',
                location_id=str(uuid.uuid4().hex),
                location_type=location_type
            )
        ]

        cls.attendance_takers = [
            CommCareUser.create(
                cls.domain, "Sauron", "123", None, None, email="sauron@email.com", location=cls.locations[0]
            ),
            CommCareUser.create(
                cls.domain, "Frodo", "123", None, None, email="frodo@email.com", location=cls.locations[1]
            )
        ]
        user_adapter.bulk_index(cls.attendance_takers, refresh=True)

        attendee_case_type = get_attendee_case_type(cls.domain)
        cls.attendees = [
            create_case(
                cls.domain,
                case_id=uuid.uuid4().hex,
                case_type=attendee_case_type,
                name='Gandalf',
                case_json={
                    LOCATION_IDS_CASE_PROPERTY: cls.locations[0].location_id
                },
                save=True
            ),
            create_case(
                cls.domain,
                case_id=uuid.uuid4().hex,
                case_type=attendee_case_type,
                name='Mary',
                case_json={
                    LOCATION_IDS_CASE_PROPERTY: cls.locations[1].location_id
                },
                save=True
            )
        ]
        case_search_adapter.bulk_index(cls.attendees, refresh=True)

    @classmethod
    def tearDownClass(cls):
        for mobile_worker in cls.attendance_takers:
            mobile_worker.delete(cls.domain, None)
        CommCareCase.objects.hard_delete_cases(cls.domain, [attendee.case_id for attendee in cls.attendees])
        SQLLocation.bulk_delete(cls.locations, None)
        super().tearDownClass()

    def test_no_location_filter(self):
        self.log_user_in(self.admin_webuser)
        response = self.client.get(self.endpoint)
        json = response.json()
        self.assertEqual(len(json['attendees']), 2)
        self.assertEqual(len(json['attendance_takers']), 3)

    def test_with_location_filter(self):
        self.log_user_in(self.admin_webuser)
        response = self.client.get(self.endpoint, {'location_id': self.locations[0].location_id})
        json = response.json()
        self.assertEqual(json['attendees'], [{'id': self.attendees[0].case_id, 'name': self.attendees[0].name}])
        self.assertEqual(
            json['attendance_takers'],
            [{'id': self.attendance_takers[0].user_id, 'name': self.attendance_takers[0].username}]
        )
