from unittest import mock

from django.test import TestCase

from corehq import privileges
from corehq.apps.data_cleaning.models.types import DataType
from corehq.apps.data_cleaning.utils.cases import (
    clear_caches_case_data_cleaning,
    get_case_property_details,
    get_property_details_from_data_dictionary,
)
from corehq.apps.data_dictionary.models import CaseProperty, CasePropertyAllowedValue
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.local_accessors import CaseType
from corehq.util.quickcache import quickcache
from corehq.util.test_utils import disable_quickcache, privilege_enabled


class BaseCaseUtilsTest(TestCase):
    domain = 'test-dc-case-utils'
    case_type = 'plant'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

    def setUp(self):
        super().setUp()
        self.case_type_dd = CaseType.objects.create(
            domain=self.domain,
            name=self.case_type,
            description='Plant case type',
        )


class GetCasePropertyDetailsForDataDictionaryTest(BaseCaseUtilsTest):
    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_text_property(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='nickname',
            label='Nickname',
            data_type=CaseProperty.DataType.PLAIN,
            index=1,
        )
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {
            'nickname': {
                'label': 'Nickname',
                'data_type': DataType.TEXT,
                'prop_id': 'nickname',
                'is_editable': True,
                'options': [],
            },
        }
        assert details == expected_result

    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_date_property(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='watered_on',
            label='Last Watered On',
            data_type=CaseProperty.DataType.DATE,
            index=1,
        )
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {
            'watered_on': {
                'label': 'Last Watered On',
                'data_type': DataType.DATE,
                'prop_id': 'watered_on',
                'is_editable': True,
                'options': [],
            },
        }
        assert details == expected_result

    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_number_property(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='height',
            label='Height (cm)',
            data_type=CaseProperty.DataType.NUMBER,
            index=1,
        )
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {
            'height': {
                'label': 'Height (cm)',
                'data_type': DataType.INTEGER,
                'prop_id': 'height',
                'is_editable': True,
                'options': [],
            },
        }
        assert details == expected_result

    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_select_property(self):
        pot_type = CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='pot_type',
            label='Pot Type',
            data_type=CaseProperty.DataType.SELECT,
            index=1,
        )
        options = ['plastic', 'ceramic', 'terracotta', 'concrete']
        for option in options:
            CasePropertyAllowedValue.objects.create(
                allowed_value=option,
                description=f'{option} pot',
                case_property=pot_type,
            )
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {
            'pot_type': {
                'label': 'Pot Type',
                'data_type': DataType.MULTIPLE_OPTION,
                'prop_id': 'pot_type',
                'is_editable': True,
                'options': options,
            },
        }
        assert details == expected_result

    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_barcode_property(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='plant_id',
            label='Plant Barcode',
            data_type=CaseProperty.DataType.BARCODE,
            index=1,
        )
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {
            'plant_id': {
                'label': 'Plant Barcode',
                'data_type': DataType.BARCODE,
                'prop_id': 'plant_id',
                'is_editable': True,
                'options': [],
            },
        }
        assert details == expected_result

    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_phone_number_property(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='contact_details',
            label='Contact Deets',
            data_type=CaseProperty.DataType.PHONE_NUMBER,
            index=1,
        )
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {
            'contact_details': {
                'label': 'Contact Deets',
                'data_type': DataType.PHONE_NUMBER,
                'prop_id': 'contact_details',
                'is_editable': True,
                'options': [],
            },
        }
        assert details == expected_result

    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_password_property(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='plant_secret',
            label='Plant Pass',
            data_type=CaseProperty.DataType.PASSWORD,
            index=1,
        )
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {
            'plant_secret': {
                'label': 'Plant Pass',
                'data_type': DataType.PASSWORD,
                'prop_id': 'plant_secret',
                'is_editable': True,
                'options': [],
            },
        }
        assert details == expected_result

    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_undefined_property(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='undefined_property',
            label='Undefined Property',
            data_type=CaseProperty.DataType.UNDEFINED,
            index=1,
        )
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {
            'undefined_property': {
                'label': 'Undefined Property',
                'data_type': DataType.TEXT,
                'prop_id': 'undefined_property',
                'is_editable': True,
                'options': [],
            },
        }
        assert details == expected_result

    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_gps_property(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='plant_location',
            label='Plant Location',
            data_type=CaseProperty.DataType.GPS,
            index=1,
        )
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {
            'plant_location': {
                'label': 'Plant Location',
                'data_type': DataType.GPS,
                'prop_id': 'plant_location',
                'is_editable': True,
                'options': [],
            },
        }
        assert details == expected_result

    @privilege_enabled(privileges.DATA_DICTIONARY)
    def test_no_properties(self):
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {}
        assert details == expected_result

    def test_no_privilege(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='plant_location',
            label='Plant Location',
            data_type=CaseProperty.DataType.GPS,
            index=1,
        )
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='undefined_property',
            label='Undefined Property',
            data_type=CaseProperty.DataType.UNDEFINED,
            index=2,
        )
        details = get_property_details_from_data_dictionary(self.domain, self.case_type)
        expected_result = {}
        assert details == expected_result


def get_mock_all_case_properties_by_domain(result_properties):
    @quickcache(vary_on=['domain', 'include_parent_properties', 'exclude_deprecated_properties'])
    def _mock_all_case_properties_by_domain(
        domain, include_parent_properties=True, exclude_deprecated_properties=True
    ):
        return result_properties

    return _mock_all_case_properties_by_domain


@privilege_enabled(privileges.DATA_DICTIONARY)
@disable_quickcache
class GetCasePropertyDetailsTest(BaseCaseUtilsTest):
    case_type = 'plant'

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [],
                'other': [],
            }
        ),
    )
    def test_text_system_property(self):
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Owner',
            'data_type': DataType.TEXT,
            'prop_id': 'owner_name',
            'is_editable': False,
            'options': None,
        }
        assert details['owner_name'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [],
                'other': [],
            }
        ),
    )
    def test_date_system_property(self):
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Date Opened',
            'data_type': DataType.DATETIME,
            'prop_id': 'date_opened',
            'is_editable': False,
            'options': None,
        }
        assert details['date_opened'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [],
                'other': [],
            }
        ),
    )
    def test_editable_system_property(self):
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'External ID',
            'data_type': DataType.TEXT,
            'prop_id': 'external_id',
            'is_editable': True,
            'options': None,
        }
        assert details['external_id'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [],
                'other': [],
            }
        ),
    )
    def test_skipped_system_property(self):
        details = get_case_property_details(self.domain, self.case_type)
        assert details.get('case_name') is None

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'not_in_dd',
                ],
                'other': [],
            }
        ),
    )
    def test_default_property_format(self):
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Not In Dd',
            'data_type': 'text',
            'prop_id': 'not_in_dd',
            'is_editable': True,
            'options': [],
        }
        assert details['not_in_dd'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'a_plant_property',
                ],
                'other': [],
            }
        ),
    )
    def test_dd_override(self):
        details = get_case_property_details(self.domain, self.case_type)
        assert details['a_plant_property']['label'] == 'A Plant Property'
        assert details['a_plant_property']['data_type'] == DataType.TEXT
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='a_plant_property',
            label='Overridden Plant Property',
            data_type=CaseProperty.DataType.NUMBER,
            index=1,
        )
        details = get_case_property_details(self.domain, self.case_type)
        assert details['a_plant_property']['label'] == 'Overridden Plant Property'
        assert details['a_plant_property']['data_type'] == DataType.INTEGER

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [],
                'other': [],
            }
        ),
    )
    def test_dd_only_property(self):
        details = get_case_property_details(self.domain, self.case_type)
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='height',
            label='Height (cm)',
            data_type=CaseProperty.DataType.NUMBER,
            index=1,
        )
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Height (cm)',
            'data_type': DataType.INTEGER,
            'prop_id': 'height',
            'is_editable': True,
            'options': [],
        }
        assert details['height'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'nickname',
                ],
                'other': [],
            }
        ),
    )
    def test_undefined_property_format(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='nickname',
            label='Plant Nickname',
            data_type=CaseProperty.DataType.UNDEFINED,
            index=1,
        )
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Plant Nickname',
            'data_type': DataType.TEXT,
            'prop_id': 'nickname',
            'is_editable': True,
            'options': [],
        }
        assert details['nickname'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'description',
                ],
                'other': [],
            }
        ),
    )
    def test_text_property_format(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='description',
            label='Plant Description',
            data_type=CaseProperty.DataType.PLAIN,
            index=1,
        )
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Plant Description',
            'data_type': DataType.TEXT,
            'prop_id': 'description',
            'is_editable': True,
            'options': [],
        }
        assert details['description'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'height',
                ],
                'other': [],
            }
        ),
    )
    def test_integer_property_format(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='height',
            label='Height (cm)',
            data_type=CaseProperty.DataType.NUMBER,
            index=1,
        )
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Height (cm)',
            'data_type': DataType.INTEGER,
            'prop_id': 'height',
            'is_editable': True,
            'options': [],
        }
        assert details['height'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'plant_location',
                ],
                'other': [],
            }
        ),
    )
    def test_gps_property_format(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='plant_location',
            label='Plant Location',
            data_type=CaseProperty.DataType.GPS,
            index=1,
        )
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Plant Location',
            'data_type': DataType.GPS,
            'prop_id': 'plant_location',
            'is_editable': True,
            'options': [],
        }
        assert details['plant_location'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'plant_barcode',
                ],
                'other': [],
            }
        ),
    )
    def test_barcode_property_format(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='plant_barcode',
            label='Plant Barcode',
            data_type=CaseProperty.DataType.BARCODE,
            index=1,
        )
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Plant Barcode',
            'data_type': DataType.BARCODE,
            'prop_id': 'plant_barcode',
            'is_editable': True,
            'options': [],
        }
        assert details['plant_barcode'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'contact_number',
                ],
                'other': [],
            }
        ),
    )
    def test_phone_number_property_format(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='contact_number',
            label='Contact Number',
            data_type=CaseProperty.DataType.PHONE_NUMBER,
            index=1,
        )
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Contact Number',
            'data_type': DataType.PHONE_NUMBER,
            'prop_id': 'contact_number',
            'is_editable': True,
            'options': [],
        }
        assert details['contact_number'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'plant_secret',
                ],
                'other': [],
            }
        ),
    )
    def test_password_property_format(self):
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='plant_secret',
            label='Plant Secret',
            data_type=CaseProperty.DataType.PASSWORD,
            index=1,
        )
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Plant Secret',
            'data_type': DataType.PASSWORD,
            'prop_id': 'plant_secret',
            'is_editable': True,
            'options': [],
        }
        assert details['plant_secret'] == expected_result

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'pot_type',
                ],
                'other': [],
            }
        ),
    )
    def test_multiple_option_property_format(self):
        pot_type = CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='pot_type',
            label='Pot Type',
            data_type=CaseProperty.DataType.SELECT,
            index=1,
        )
        options = ['plastic', 'ceramic', 'terracotta', 'concrete']
        for option in options:
            CasePropertyAllowedValue.objects.create(
                allowed_value=option,
                description=f'{option} pot',
                case_property=pot_type,
            )
        details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Pot Type',
            'data_type': DataType.MULTIPLE_OPTION,
            'prop_id': 'pot_type',
            'is_editable': True,
            'options': options,
        }
        assert details['pot_type'] == expected_result


@privilege_enabled(privileges.DATA_DICTIONARY)
class ClearCachesTest(BaseCaseUtilsTest):
    case_type = 'plant'

    @mock.patch(
        'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
        get_mock_all_case_properties_by_domain(
            {
                case_type: [
                    'height',
                ],
                'other': [],
            }
        ),
    )
    def test_clear_caches(self):
        clear_caches_case_data_cleaning(self.domain, self.case_type)
        first_details = get_case_property_details(self.domain, self.case_type)
        expected_result = {
            'label': 'Height',
            'data_type': DataType.TEXT,
            'prop_id': 'height',
            'is_editable': True,
            'options': [],
        }
        assert first_details['height'] == expected_result
        CaseProperty.objects.create(
            case_type=self.case_type_dd,
            name='height',
            label='Height (cm)',
            data_type=CaseProperty.DataType.NUMBER,
            index=1,
        )
        details = get_case_property_details(self.domain, self.case_type)
        assert details == first_details
        clear_caches_case_data_cleaning(self.domain, self.case_type)
        details = get_case_property_details(self.domain, self.case_type)
        assert details != first_details
        assert details['height']['label'] == 'Height (cm)'
        assert details['height']['data_type'] == DataType.INTEGER
