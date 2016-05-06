from django.test import TestCase
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.reminders.models import (CaseReminder, CaseReminderHandler,
    RECIPIENT_CASE_OWNER_LOCATION_PARENT)
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import create_test_case
from mock import patch


class ReminderRecipientTest(TestCase):
    domain = 'reminder-recipient-test'

    def setUp(self):
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()

    def tearDown(self):
        self.domain_obj.delete()

    @run_with_all_backends
    def test_recipient_case_owner_location_parent(self):
        parent_location_type = LocationType.objects.create(
            domain=self.domain,
            name='parent type',
            code='parent'
        )

        child_location_type = LocationType.objects.create(
            domain=self.domain,
            name='child type',
            code='child',
            parent_type=parent_location_type
        )

        parent_location = SQLLocation.objects.create(
            domain=self.domain,
            name='parent test',
            site_code='parent',
            location_type=parent_location_type
        )

        child_location = SQLLocation.objects.create(
            domain=self.domain,
            name='child test',
            site_code='child',
            location_type=child_location_type,
            parent=parent_location
        )

        user = CommCareUser.create(self.domain, 'test', 'test')
        user.location_id = child_location.location_id
        user.save()

        with create_test_case(self.domain, 'test-case', 'test-name', owner_id=user.get_id) as case:
            self.assertEqual(case.owner_id, user.get_id)
            handler = CaseReminderHandler(domain=self.domain, recipient=RECIPIENT_CASE_OWNER_LOCATION_PARENT)
            reminder = CaseReminder(domain=self.domain, case_id=case.case_id)

            # Test the recipient is returned correctly
            with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler):
                self.assertEqual(reminder.recipient, [parent_location])

            # Remove parent location
            parent_location.delete()
            child_location.parent = None
            child_location.save()
            with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler):
                self.assertIsNone(reminder.recipient)

            # Remove child location
            child_location.delete()
            user.location_id = None
            user.save()
            with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler):
                self.assertIsNone(reminder.recipient)

            # Remove case
            reminder.case_id = None
            with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler):
                self.assertIsNone(reminder.recipient)

        parent_location_type.delete()
        child_location_type.delete()
        user.delete()
