from unittest import mock

from django.test import TestCase

from corehq import privileges
from corehq.apps.data_cleaning.utils.cases import clear_caches_case_data_cleaning, get_case_property_details
from corehq.apps.data_dictionary.models import CaseProperty, CasePropertyAllowedValue
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.local_accessors import CaseType
from corehq.apps.users.models import WebUser
from corehq.util.quickcache import quickcache
from corehq.util.test_utils import privilege_enabled


@quickcache(vary_on=['domain', 'include_parent_properties', 'exclude_deprecated_properties'])
def _mock_all_case_properties_by_domain(
    domain,
    include_parent_properties=True,
    exclude_deprecated_properties=True,
):
    return SAMPLE_PROPERTIES


class GetCasePropertyDetailsTest(TestCase):
    domain = 'test-dc-case-prop-details'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.web_user = WebUser.create(cls.domain, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.addClassCleanup(cls.web_user.delete, cls.domain, deleted_by=None)

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        _mock_all_case_properties_by_domain,
    )
    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_expected_format_no_dd_entries(self):
        clear_caches_case_data_cleaning(self.domain, 'plant')
        details = get_case_property_details(
            self.domain,
            'plant',
        )
        assert details == PLANT_DETAILS_NO_DD

    def _generate_data_dictionary_entries(self):
        case_type = CaseType.objects.create(
            domain=self.domain,
            name='plant',
            description='Plant case type',
        )
        property_defs = [
            ('height', 'Height (cm)', CaseProperty.DataType.NUMBER),
            ('pot_type', 'Pot Type', CaseProperty.DataType.SELECT),
            ('last_watered_on', 'Watered On', CaseProperty.DataType.DATE),
            ('plant_id', 'Plant Barcode', CaseProperty.DataType.BARCODE),
            ('contact_details', 'Contact Deets', CaseProperty.DataType.PHONE_NUMBER),
            ('plant_secret', 'Plant Pass', CaseProperty.DataType.PASSWORD),
        ]
        for index, (name, label, data_type) in enumerate(property_defs):
            CaseProperty.objects.create(
                case_type=case_type,
                name=name,
                label=label,
                data_type=data_type,
                index=index,
            )
        pot_type = case_type.properties.get(name='pot_type')
        options = ['plastic', 'ceramic', 'terracotta', 'concrete']
        for option in options:
            CasePropertyAllowedValue.objects.create(
                allowed_value=option,
                description=f'{option} pot',
                case_property=pot_type,
            )

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        _mock_all_case_properties_by_domain,
    )
    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_expected_format_with_dd_entries(self):
        clear_caches_case_data_cleaning(self.domain, 'plant')
        self._generate_data_dictionary_entries()
        details = get_case_property_details(
            self.domain,
            'plant',
        )
        assert details == PLANT_DETAILS_WITH_DD

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        _mock_all_case_properties_by_domain,
    )
    def test_expected_format_without_dd_access(self):
        clear_caches_case_data_cleaning(self.domain, 'plant')
        self._generate_data_dictionary_entries()
        details = get_case_property_details(
            self.domain,
            'plant',
        )
        assert details == PLANT_DETAILS_NO_DD

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        _mock_all_case_properties_by_domain,
    )
    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_expected_value_with_caches(self):
        clear_caches_case_data_cleaning(self.domain, 'plant')
        details = get_case_property_details(
            self.domain,
            'plant',
        )
        assert details == PLANT_DETAILS_NO_DD
        self._generate_data_dictionary_entries()
        details = get_case_property_details(
            self.domain,
            'plant',
        )
        assert details == PLANT_DETAILS_NO_DD
        clear_caches_case_data_cleaning(self.domain, 'plant')
        details = get_case_property_details(
            self.domain,
            'plant',
        )
        assert details == PLANT_DETAILS_WITH_DD


SAMPLE_PROPERTIES = {
    'plant': [
        'height',
        'last_watered_on',
        'name',
        'nickname',
        'pot_type',
        'plant_id',
        'plant_location',
        'contact_details',
        'plant_secret',
    ],
    'plant_room': [
        'description',
        'distance_from_window_cm',
        'light_level',
        'min_water_required',
        'name',
        'plant_surfaces',
        'room_barcode',
        'room_id',
        'room_location',
        'water_ratio',
    ],
    'commcare-user': ['name'],
}

PLANT_DETAILS_NO_DD = {
    'name': {
        'label': 'Name',
        'data_type': 'text',
        'prop_id': 'name',
        'is_editable': False,
        'options': None,
    },
    'contact_details': {
        'label': 'Contact Details',
        'data_type': 'text',
        'prop_id': 'contact_details',
        'is_editable': True,
        'options': None,
    },
    'nickname': {
        'label': 'Nickname',
        'data_type': 'text',
        'prop_id': 'nickname',
        'is_editable': True,
        'options': None,
    },
    'plant_location': {
        'label': 'Plant Location',
        'data_type': 'text',
        'prop_id': 'plant_location',
        'is_editable': True,
        'options': None,
    },
    'last_watered_on': {
        'label': 'Last Watered On',
        'data_type': 'text',
        'prop_id': 'last_watered_on',
        'is_editable': True,
        'options': None,
    },
    'pot_type': {
        'label': 'Pot Type',
        'data_type': 'text',
        'prop_id': 'pot_type',
        'is_editable': True,
        'options': None,
    },
    'height': {
        'label': 'Height',
        'data_type': 'text',
        'prop_id': 'height',
        'is_editable': True,
        'options': None,
    },
    'plant_id': {
        'label': 'Plant Id',
        'data_type': 'text',
        'prop_id': 'plant_id',
        'is_editable': True,
        'options': None,
    },
    'plant_secret': {
        'label': 'Plant Secret',
        'data_type': 'text',
        'prop_id': 'plant_secret',
        'is_editable': True,
        'options': None,
    },
    '@case_id': {
        'label': 'Case ID',
        'data_type': 'text',
        'prop_id': '@case_id',
        'is_editable': False,
        'options': None,
    },
    '@case_type': {
        'label': 'Case Type',
        'data_type': 'text',
        'prop_id': '@case_type',
        'is_editable': False,
        'options': None,
    },
    '@owner_id': {
        'label': 'Owner ID',
        'data_type': 'text',
        'prop_id': '@owner_id',
        'is_editable': False,
        'options': None,
    },
    '@status': {
        'label': 'Open/Closed Status',
        'data_type': 'text',
        'prop_id': '@status',
        'is_editable': False,
        'options': None,
    },
    'external_id': {
        'label': 'External ID',
        'data_type': 'text',
        'prop_id': 'external_id',
        'is_editable': True,
        'options': None,
    },
    'date_opened': {
        'label': 'Date Opened',
        'data_type': 'datetime',
        'prop_id': 'date_opened',
        'is_editable': False,
        'options': None,
    },
    'closed_on': {
        'label': 'Closed On',
        'data_type': 'datetime',
        'prop_id': 'closed_on',
        'is_editable': False,
        'options': None,
    },
    'last_modified': {
        'label': 'Last Modified On',
        'data_type': 'datetime',
        'prop_id': 'last_modified',
        'is_editable': False,
        'options': None,
    },
    'closed_by_username': {
        'label': 'Closed By',
        'data_type': 'text',
        'prop_id': 'closed_by_username',
        'is_editable': False,
        'options': None,
    },
    'last_modified_by_user_username': {
        'label': 'Last Modified By',
        'data_type': 'text',
        'prop_id': 'last_modified_by_user_username',
        'is_editable': False,
        'options': None,
    },
    'opened_by_username': {
        'label': 'Opened By',
        'data_type': 'text',
        'prop_id': 'opened_by_username',
        'is_editable': False,
        'options': None,
    },
    'owner_name': {
        'label': 'Owner',
        'data_type': 'text',
        'prop_id': 'owner_name',
        'is_editable': False,
        'options': None,
    },
    'closed_by_user_id': {
        'label': 'Closed By User ID',
        'data_type': 'text',
        'prop_id': 'closed_by_user_id',
        'is_editable': False,
        'options': None,
    },
    'opened_by_user_id': {
        'label': 'Opened By User ID',
        'data_type': 'text',
        'prop_id': 'opened_by_user_id',
        'is_editable': False,
        'options': None,
    },
    'server_last_modified_date': {
        'label': 'Last Modified (UTC)',
        'data_type': 'datetime',
        'prop_id': 'server_last_modified_date',
        'is_editable': False,
        'options': None,
    },
}

PLANT_DETAILS_WITH_DD = {
    'pot_type': {
        'label': 'Pot Type',
        'data_type': 'multiple_option',
        'prop_id': 'pot_type',
        'is_editable': True,
        'options': ['plastic', 'ceramic', 'terracotta', 'concrete'],
    },
    'plant_secret': {
        'label': 'Plant Pass',
        'data_type': 'password',
        'prop_id': 'plant_secret',
        'is_editable': True,
        'options': [],
    },
    'plant_location': {
        'label': 'Plant Location',
        'data_type': 'text',
        'prop_id': 'plant_location',
        'is_editable': True,
        'options': None,
    },
    'nickname': {
        'label': 'Nickname',
        'data_type': 'text',
        'prop_id': 'nickname',
        'is_editable': True,
        'options': None,
    },
    'height': {
        'label': 'Height (cm)',
        'data_type': 'integer',
        'prop_id': 'height',
        'is_editable': True,
        'options': [],
    },
    'plant_id': {
        'label': 'Plant Barcode',
        'data_type': 'barcode',
        'prop_id': 'plant_id',
        'is_editable': True,
        'options': [],
    },
    'name': {
        'label': 'Name',
        'data_type': 'text',
        'prop_id': 'name',
        'is_editable': False,
        'options': None,
    },
    'last_watered_on': {
        'label': 'Watered On',
        'data_type': 'date',
        'prop_id': 'last_watered_on',
        'is_editable': True,
        'options': [],
    },
    'contact_details': {
        'label': 'Contact Deets',
        'data_type': 'phone_number',
        'prop_id': 'contact_details',
        'is_editable': True,
        'options': [],
    },
    '@case_id': {
        'label': 'Case ID',
        'data_type': 'text',
        'prop_id': '@case_id',
        'is_editable': False,
        'options': None,
    },
    '@case_type': {
        'label': 'Case Type',
        'data_type': 'text',
        'prop_id': '@case_type',
        'is_editable': False,
        'options': None,
    },
    '@owner_id': {
        'label': 'Owner ID',
        'data_type': 'text',
        'prop_id': '@owner_id',
        'is_editable': False,
        'options': None,
    },
    '@status': {
        'label': 'Open/Closed Status',
        'data_type': 'text',
        'prop_id': '@status',
        'is_editable': False,
        'options': None,
    },
    'external_id': {
        'label': 'External ID',
        'data_type': 'text',
        'prop_id': 'external_id',
        'is_editable': True,
        'options': None,
    },
    'date_opened': {
        'label': 'Date Opened',
        'data_type': 'datetime',
        'prop_id': 'date_opened',
        'is_editable': False,
        'options': None,
    },
    'closed_on': {
        'label': 'Closed On',
        'data_type': 'datetime',
        'prop_id': 'closed_on',
        'is_editable': False,
        'options': None,
    },
    'last_modified': {
        'label': 'Last Modified On',
        'data_type': 'datetime',
        'prop_id': 'last_modified',
        'is_editable': False,
        'options': None,
    },
    'closed_by_username': {
        'label': 'Closed By',
        'data_type': 'text',
        'prop_id': 'closed_by_username',
        'is_editable': False,
        'options': None,
    },
    'last_modified_by_user_username': {
        'label': 'Last Modified By',
        'data_type': 'text',
        'prop_id': 'last_modified_by_user_username',
        'is_editable': False,
        'options': None,
    },
    'opened_by_username': {
        'label': 'Opened By',
        'data_type': 'text',
        'prop_id': 'opened_by_username',
        'is_editable': False,
        'options': None,
    },
    'owner_name': {
        'label': 'Owner',
        'data_type': 'text',
        'prop_id': 'owner_name',
        'is_editable': False,
        'options': None,
    },
    'closed_by_user_id': {
        'label': 'Closed By User ID',
        'data_type': 'text',
        'prop_id': 'closed_by_user_id',
        'is_editable': False,
        'options': None,
    },
    'opened_by_user_id': {
        'label': 'Opened By User ID',
        'data_type': 'text',
        'prop_id': 'opened_by_user_id',
        'is_editable': False,
        'options': None,
    },
    'server_last_modified_date': {
        'label': 'Last Modified (UTC)',
        'data_type': 'datetime',
        'prop_id': 'server_last_modified_date',
        'is_editable': False,
        'options': None,
    },
}
