from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.apps.users.models import (
    CommCareUser,
    HqPermissions,
    UserRole,
    WebUser,
)
from corehq.apps.users.role_utils import UserRolePresets
from corehq.form_processor.models import CommCareCase

from ..models import AttendeeModel, get_attendee_case_type
from ..tasks import (
    close_mobile_worker_attendee_cases,
    get_user_attendee_models_on_domain,
    sync_mobile_worker_attendees,
)


class TestTasks(TestCase):

    domain = 'hogwards'
    web_username = 'harry_potter'
    password = 'chamber_of_secrets'

    def setUp(self) -> None:
        super().setUp()
        self.domain_obj = create_domain(self.domain)
        self.webuser = WebUser.create(
            self.domain,
            self.web_username,
            self.password,
            None,
            None,
            is_admin=False,
        )
        role = self.attendance_coordinator_role()
        self.webuser.set_role(self.domain, role.get_qualified_id())
        self.webuser.save()
        self._create_mobile_worker("Snape")
        self._create_mobile_worker("Dumbledore")

    def attendance_coordinator_role(self):
        return UserRole.create(
            self.domain,
            UserRolePresets.ATTENDANCE_COORDINATOR,
            permissions=HqPermissions(manage_attendance_tracking=True),
        )

    def _create_mobile_worker(self, username):
        return CommCareUser.create(
            domain=self.domain,
            username=username,
            password="*****",
            created_by=None,
            created_via=None,
            metadata=None,
        )

    def tearDown(self):
        self.webuser.delete(None, None)
        self.domain_obj.delete()

        user_roles = UserRole.objects.filter(
            name=UserRolePresets.ATTENDANCE_COORDINATOR, domain=self.domain
        )
        if user_roles:
            user_roles[0].delete()

        super().tearDown()

    def test_cases_created_for_mobile_workers(self):
        """Test that the `sync_mobile_worker_attendees` task creates `commcare-attendee` cases for mobile
        workers.
        """
        user_id_model_mapping = get_user_attendee_models_on_domain(self.domain)
        self.assertEqual(len(user_id_model_mapping), 0)

        sync_mobile_worker_attendees(self.domain, user_id=self.webuser.user_id)
        user_id_model_mapping = get_user_attendee_models_on_domain(self.domain)
        self.assertEqual(len(user_id_model_mapping), 2)

        mobile_worker_attendee_models = (
            model for model in AttendeeModel.objects.by_domain(self.domain)
            if model.user_id
        )
        for model in mobile_worker_attendee_models:
            commcare_user_id = model.user_id
            commcare_user = CommCareUser.get_by_user_id(commcare_user_id)
            # The case_name for mobile workers should be their username
            self.assertEqual(model.name, commcare_user.username.split('@')[0])

    def test_duplicate_cases_not_created(self):
        # Let's call this to create initial cases
        sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)

        # Get the case count
        models = AttendeeModel.objects.by_domain(self.domain, include_closed=True)
        case_count_before = len(models)

        # Now call the task again, which should not create new cases
        sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)

        # Check total case count again
        models = AttendeeModel.objects.by_domain(self.domain, include_closed=True)
        case_count = len(models)
        self.assertEqual(case_count, case_count_before)

    def test_closed_cases_reopened_for_mobile_workers(self):
        """Test that the `sync_mobile_worker_attendees` task reopens closed attendee cases associated with
        mobile workers
        """
        sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)

        # Close the current attendee cases for mobile workers
        self._assert_cases_state(closed=False)

        self._close_mobile_worker_attendee_cases()

        # Let's just make sure they are closed
        self._assert_cases_state(closed=True)

        # Now call the task again, which should reopen the cases
        sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)

        self._assert_cases_state(closed=False)

    def test_mobile_worker_attendee_cases_closed(self):
        """Only mobile worker attendee cases should be closed, not all attendee cases"""
        # Create some mobile worker attendee cases
        sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)

        # Let's add another attendee case, not associated with any mobile worker
        self._create_non_mobile_worker_attendee_case()

        # Let's make sure they're all open
        models = AttendeeModel.objects.by_domain(self.domain, include_closed=True)
        are_mobile_workers = [m for m in models if m.user_id]
        are_not_mobile_workers = [m for m in models if not m.user_id]
        self.assertEqual(len(models), 3)
        self.assertEqual(len(are_mobile_workers), 2)
        self.assertEqual(len(are_not_mobile_workers), 1)
        self.assertTrue(all(not m.case.closed for m in models))

        # Now close mobile worker cases
        close_mobile_worker_attendee_cases(domain_name=self.domain)

        # Only those with the `ATTENDEE_USER_ID_CASE_PROPERTY` property should be closed
        models = AttendeeModel.objects.by_domain(self.domain, include_closed=True)
        for model in models:
            if model.user_id:
                self.assertTrue(model.case.closed)
            else:
                self.assertFalse(model.case.closed)

    def _close_mobile_worker_attendee_cases(self):
        case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type(
            domain=self.domain,
            case_type=get_attendee_case_type(self.domain)
        )
        for case_id in case_ids:
            helper = CaseHelper(case_id=case_id, domain=self.domain)
            helper.close(user_id=self.webuser.user_id)

    def _assert_cases_state(self, closed=False):
        """Loop through attendee cases associated with mobile workers and asserts if the cases are open
        or closed
        """
        assert_method = self.assertTrue if closed else self.assertFalse
        for model in AttendeeModel.objects.by_domain(self.domain, include_closed=True):
            assert_method(model.case.closed)

    def _create_non_mobile_worker_attendee_case(self):
        helper = CaseHelper(domain=self.domain)
        helper.create_case({
            'case_name': "Court Case",
            'case_type': get_attendee_case_type(self.domain),
        })
