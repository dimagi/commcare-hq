from django.test import SimpleTestCase

from corehq.apps.integration.kyc.models import KycConfig, UserDataStore
from corehq.apps.integration.kyc.tables import KycVerifyTable


class TestKycVerifyTable(SimpleTestCase):
    domain = 'test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kyc_config = KycConfig(
            domain=cls.domain,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
            api_field_to_user_data_map={
                'pants_type': 'apple_bottom_jeans',
                'shoe_type': 'boots_with_fur',
                'test': {
                    'data_field': 'foo',
                },
                'incorrect_field': {
                    'data_feild': 'bar'
                }
            }
        )

    def test_get_extra_columns(self):
        extra_cols = KycVerifyTable.get_extra_columns(self.kyc_config)
        expected_data = [
            ('apple_bottom_jeans', 'Apple Bottom Jeans'),
            ('boots_with_fur', 'Boots With Fur'),
            ('foo', 'Foo'),
            ('kyc_verification_status', 'KYC Status'),
            ('kyc_last_verified_at', 'Last Verified'),
            ('verify_btn', 'Verify')
        ]
        for i, (name, verbose_name) in enumerate(expected_data):
            assert extra_cols[i][0] == name
            assert extra_cols[i][1].verbose_name == verbose_name
