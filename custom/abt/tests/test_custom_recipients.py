from django.test import TestCase
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.messaging.scheduling.scheduling_partitioned.models import CaseTimedScheduleInstance
from corehq.util.test_utils import create_test_case


class CustomRecipientTest(TestCase):

    def setUp(self):
        self.domain = 'custom-recipient-test'
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

        self.parent_location = SQLLocation.objects.create(
            domain=self.domain,
            name='parent test',
            site_code='parent',
            location_type=self.parent_location_type
        )

        self.child_location = SQLLocation.objects.create(
            domain=self.domain,
            name='child test',
            site_code='child',
            location_type=self.child_location_type,
            parent=self.parent_location
        )

        self.user = CommCareUser.create(self.domain, 'test', 'test')
        self.user.set_location(self.child_location)

    def tearDown(self):
        self.user.delete()
        self.child_location.delete()
        self.parent_location.delete()
        self.child_location_type.delete()
        self.parent_location_type.delete()
        self.domain_obj.delete()

    @run_with_all_backends
    def test_recipient_case_owner_location_parent(self):
        with create_test_case(self.domain, 'test-case', 'test-name', owner_id=self.user.get_id) as case:
            self.assertEqual(case.owner_id, self.user.get_id)

            def instance(case_id=''):
                # recipient is memoized
                return CaseTimedScheduleInstance(
                    domain=self.domain,
                    case_id=case_id or case.case_id,
                    recipient_type='CustomRecipient',
                    recipient_id='CASE_OWNER_LOCATION_PARENT'
                )

            # Test the recipient is returned correctly
            self.assertTrue(isinstance(instance().recipient, SQLLocation))
            self.assertEqual(instance().recipient.pk, self.parent_location.pk)

            # Test when the user's location has no parent location
            self.user.set_location(self.parent_location)
            self.assertIsNone(instance().recipient)

            # Remove child location
            self.user.unset_location()
            self.assertIsNone(instance().recipient)

            # Remove case
            self.assertIsNone(instance(case_id='does-not-exist').recipient)
