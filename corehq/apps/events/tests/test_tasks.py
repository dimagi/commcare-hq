from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.events.models import AttendeeCase, ATTENDEE_USER_ID_CASE_PROPERTY
from corehq.apps.events.tasks import get_existing_cases_by_user_ids
from corehq.apps.events import tasks
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.role_utils import UserRolePresets
from django.test import TestCase
import uuid
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseBlock
from corehq.apps.events.models import get_attendee_case_type


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
        workers
        """
        user_id_case_mapping = get_existing_cases_by_user_ids(self.domain)
        user_ids = list(user_id_case_mapping.keys())
        tasks.sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)
        user_id_case_mapping = get_existing_cases_by_user_ids(self.domain)
        user_ids = list(user_id_case_mapping.keys())

        self.assertEqual(len(user_ids), 2)

    def test_duplicate_cases_not_created(self):
        # Let's call this to create initial cases
        tasks.sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)

        # Get the case count
        cases = AttendeeCase.objects.by_domain(self.domain, include_closed=True)
        case_count_before = len(cases)

        # Now call the task again, which should not create new cases
        tasks.sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)

        # Check total case count again
        cases = AttendeeCase.objects.by_domain(self.domain, include_closed=True)
        case_count = len(cases)
        self.assertEqual(case_count, case_count_before)

    def test_closed_cases_reopened_for_mobile_workers(self):
        """Test that the `sync_mobile_worker_attendees` task reopens closed attendee cases associated with
        mobile workers
        """
        tasks.sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)

        # Close the current attendee cases for mobile workers
        self._assert_cases_state(closed=False)

        self._close_mobile_worker_attendee_cases()

        # Let's just make sure they are closed
        self._assert_cases_state(closed=True)

        # Now call the task again, which should reopen the cases
        tasks.sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)

        self._assert_cases_state(closed=False)

    def test_mobile_worker_attendee_cases_closed(self):
        """Only mobile worker attendee cases should be closed, not all attendee cases"""
        # Create some mobile worker attendee cases
        tasks.sync_mobile_worker_attendees(domain_name=self.domain, user_id=self.webuser.user_id)

        # Let's add another attendee case, not associated with any mobile worker
        self._create_non_mobile_worker_attendee_case()

        # Let's make sure they're all open
        user_id_case_mapping = get_existing_cases_by_user_ids(self.domain)
        self.assertEqual(len(user_id_case_mapping), 3)

        for case in user_id_case_mapping.values():
            self.assertFalse(case.closed)

        # Now close mobile worker cases
        tasks.close_mobile_worker_attendee_cases(domain_name=self.domain)

        # Only those with the `ATTENDEE_USER_ID_CASE_PROPERTY` property should be closed
        user_id_case_mapping = get_existing_cases_by_user_ids(self.domain)
        for case in user_id_case_mapping.values():
            if case.get_case_property(ATTENDEE_USER_ID_CASE_PROPERTY):
                self.assertTrue(case.closed)
            else:
                self.assertFalse(case.closed)

    def _close_mobile_worker_attendee_cases(self):
        from corehq.apps.hqcase.api.updates import JsonCaseUpdate, CaseIDLookerUpper
        from corehq.apps.hqcase.utils import submit_case_blocks

        cases = AttendeeCase.objects.by_domain(self.domain, include_closed=True)
        updates = []
        data = {
            "close": True,
            "user_id": self.webuser.user_id,
        }
        for case in cases:
            data['case_id'] = case.case_id
            update = JsonCaseUpdate.wrap(data)
            updates.append(update)
        case_db = CaseIDLookerUpper(self.domain, updates)
        case_blocks = [update.get_caseblock(case_db) for update in updates]
        submit_case_blocks(case_blocks, domain=self.domain, user_id=self.webuser.user_id)

    def _assert_cases_state(self, closed=False):
        """Loop through attendee cases associated with mobile workers and asserts if the cases are open
        or closed
        """
        cases = AttendeeCase.objects.by_domain(self.domain, include_closed=True)
        assert_method = self.assertTrue
        if not closed:
            assert_method = self.assertFalse
        for case in cases:
            assert_method(case.closed)

    @classmethod
    def _create_non_mobile_worker_attendee_case(self):
        case_id = uuid.uuid4().hex
        caseblock = CaseBlock(
            case_id=case_id,
            case_type=get_attendee_case_type(self.domain),
            case_name="Court Case",
        )
        submit_case_blocks(caseblock.as_text(), domain=self.domain)
