from corehq.apps.locations.models import Location
from custom.ilsgateway.models import DeliveryGroups
from custom.ilsgateway.tests.handlers.utils import ILSTestScript, TEST_DOMAIN
from custom.ilsgateway.utils import get_sql_locations_by_domain_and_group


class TestDeliveryGroups(ILSTestScript):

    def test_delivery_group_basic(self):
        submitting_group = DeliveryGroups().current_submitting_group()
        original_submitting = len(list(get_sql_locations_by_domain_and_group(
            TEST_DOMAIN,
            submitting_group
        )))

        for location in Location.by_domain(TEST_DOMAIN):
            if location.metadata.get('group') != submitting_group:
                location.metadata['group'] = submitting_group
                location.save()
                break

        new_submitting = len(list(get_sql_locations_by_domain_and_group(
            TEST_DOMAIN,
            submitting_group
        )))
        self.assertEqual(original_submitting + 1, new_submitting)
