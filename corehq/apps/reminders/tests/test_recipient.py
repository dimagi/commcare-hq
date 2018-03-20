from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import update_case
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.reminders.models import CaseReminder, CaseReminderHandler
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import create_test_case, set_parent_case
from mock import patch


class ReminderRecipientTest(TestCase):
    domain = 'reminder-recipient-test'

    def setUp(self):
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()

        self.parent_location_type = LocationType.objects.create(
            domain=self.domain,
            name='parent type',
            code='parent'
        )

        self.child_location_type = LocationType.objects.create(
            domain=self.domain,
            name='child type',
            code='child',
            parent_type=self.parent_location_type
        )

        self.user = CommCareUser.create(self.domain, 'test', 'test')

    def tearDown(self):
        self.parent_location_type.delete()
        self.child_location_type.delete()
        self.user.delete()
        self.domain_obj.delete()

    @run_with_all_backends
    def test_recipient_case_owner_location_parent(self):
        parent_location = SQLLocation.objects.create(
            domain=self.domain,
            name='parent test',
            site_code='parent',
            location_type=self.parent_location_type
        )
        self.addCleanup(parent_location.delete)

        child_location = SQLLocation.objects.create(
            domain=self.domain,
            name='child test',
            site_code='child',
            location_type=self.child_location_type,
            parent=parent_location
        )
        self.addCleanup(child_location.delete)

        self.user.set_location(child_location)

        with create_test_case(self.domain, 'test-case', 'test-name', owner_id=self.user.get_id) as case:
            self.assertEqual(case.owner_id, self.user.get_id)
            handler = CaseReminderHandler(domain=self.domain, recipient='CASE_OWNER_LOCATION_PARENT')
            reminder = CaseReminder(domain=self.domain, case_id=case.case_id)

            # Test the recipient is returned correctly
            with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler):
                self.assertEqual(reminder.recipient, [parent_location])

            # Remove parent location
            child_location.parent = None
            child_location.save()
            with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler):
                self.assertIsNone(reminder.recipient)

            # Remove child location
            self.user.unset_location()
            with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler):
                self.assertIsNone(reminder.recipient)

            # Remove case
            reminder.case_id = None
            with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler):
                self.assertIsNone(reminder.recipient)

    @run_with_all_backends
    def test_host_case_owner_location(self):
        parent_location = SQLLocation.objects.create(
            domain=self.domain,
            name='parent test',
            site_code='parent',
            location_type=self.parent_location_type
        )
        self.addCleanup(parent_location.delete)

        child_location = SQLLocation.objects.create(
            domain=self.domain,
            name='child test',
            site_code='child',
            location_type=self.child_location_type,
            parent=parent_location
        )
        self.addCleanup(child_location.delete)

        with create_test_case(self.domain, 'test-extension-case', 'name') as extension_case:
            with create_test_case(self.domain, 'test-host-case', 'name') as host_case:

                update_case(self.domain, host_case.case_id,
                    case_properties={'owner_id': child_location.location_id})
                set_parent_case(self.domain, extension_case, host_case, relationship='extension')

                handler1 = CaseReminderHandler(domain=self.domain, recipient='HOST_CASE_OWNER_LOCATION')
                handler2 = CaseReminderHandler(domain=self.domain, recipient='HOST_CASE_OWNER_LOCATION_PARENT')
                reminder = CaseReminder(domain=self.domain, case_id=extension_case.case_id)

                # Test the recipients are returned correctly
                with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler1):
                    self.assertEqual(reminder.recipient, [child_location])

                with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler2):
                    self.assertEqual(reminder.recipient, [parent_location])

                # Remove parent location reference
                child_location.parent = None
                child_location.save()
                with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler2):
                    self.assertIsNone(reminder.recipient)

                # Test location that does not exist
                update_case(self.domain, host_case.case_id, case_properties={'owner_id': 'does-not-exist'})
                with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler1):
                    self.assertIsNone(reminder.recipient)

                # Test on a case that is not an extension case
                reminder.case_id = host_case.case_id
                with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler1):
                    self.assertIsNone(reminder.recipient)

                # Test on a blank case id
                reminder.case_id = None
                with patch('corehq.apps.reminders.models.CaseReminder.handler', new=handler1):
                    self.assertIsNone(reminder.recipient)
