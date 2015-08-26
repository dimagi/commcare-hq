from django.test import TestCase
from corehq import Domain
from corehq.apps.locations.models import LocationType, Location
from corehq.apps.products.models import Product
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.models import FacilityInCharge


class TestDeleteDomain(TestCase):

    def _create_data(self, domain_name):
        product = Product(domain=domain_name, name='test-product')
        product.save()

        location = Location(
            domain=domain_name,
            site_code='testcode',
            name='test1',
            location_type='facility'
        )
        location.save()
        self.locations[domain_name] = location.sql_location

        user = CommCareUser.create(
            domain=domain_name,
            username='test-{}'.format(domain_name),
            password='dummy'
        )

        FacilityInCharge.objects.create(
            user_id=user.get_id,
            location=location.sql_location
        )

    def setUp(self):
        self.domain = Domain(name="test", is_active=True)
        self.domain.save()
        self.domain2 = Domain(name="test2", is_active=True)
        self.domain2.save()
        self.locations = {}
        LocationType.objects.create(
            domain='test',
            name='facility',
        )
        LocationType.objects.create(
            domain='test2',
            name='facility',
        )

        self._create_data('test')
        self._create_data('test2')

    def test_pre_delete_signal_receiver(self):
        self.domain.delete()

        self.assertEqual(FacilityInCharge.objects.filter(location=self.locations['test']).count(), 0)
        self.assertEqual(FacilityInCharge.objects.filter(location=self.locations['test2']).count(), 1)

    def tearDown(self):
        self.domain2.delete()
