from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.reminders.models import (CaseReminder, CaseReminderHandler,
    RECIPIENT_CASE_OWNER_LOCATION_PARENT)
from corehq.apps.users.models import CommCareUser
from mock import patch


class ReminderRecipientTest(TestCase):
    domain = 'reminder-recipient-test'

    def test_recipient_case_owner_location_parent(self):
        domain_obj = Domain(name=self.domain)
        domain_obj.save()
        self.addCleanup(domain_obj.delete)

        parent_location_type = LocationType.objects.create(
            domain=self.domain,
            name='parent type',
            code='parent'
        )
        self.addCleanup(parent_location_type.delete)

        child_location_type = LocationType.objects.create(
            domain=self.domain,
            name='child type',
            code='child',
            parent_type=parent_location_type
        )
        self.addCleanup(child_location_type.delete)

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
        self.addCleanup(user.delete)

        case = CommCareCase(domain=self.domain, owner_id=user.get_id)
        case.save()
        self.addCleanup(case.delete)

        handler = CaseReminderHandler(domain=self.domain, recipient=RECIPIENT_CASE_OWNER_LOCATION_PARENT)
        reminder = CaseReminder(domain=self.domain, case_id=case.get_id)

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
