from django.test import SimpleTestCase
from corehq.apps.domain.models import Domain, CallCenterProperties
from corehq.apps.callcenter.fixturegenerators import IndicatorsFixturesProvider


class TestUseFixturesConfig(SimpleTestCase):

    def test_fixture_provider(self):
        provider = IndicatorsFixturesProvider()
        domain = Domain(
            call_center_config=CallCenterProperties(
                enabled=True,
                case_owner_id="bar",
                case_type="baz",
            )
        )

        domain.call_center_config.use_fixtures = False
        self.assertTrue(provider._should_return_no_fixtures(domain, None))

        domain.call_center_config.use_fixtures = True
        self.assertFalse(provider._should_return_no_fixtures(domain, None))
