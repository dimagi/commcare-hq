from django.test import TestCase

from corehq.apps.case_search.endpoint_capability import (
    FIELD_TYPE_DATE,
    FIELD_TYPE_GEOPOINT,
    FIELD_TYPE_NUMBER,
    FIELD_TYPE_SELECT,
    FIELD_TYPE_TEXT,
    get_capability,
    get_field_type,
    get_operations_for_field_type,
)
from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyAllowedValue,
    CaseType,
)


class TestGetFieldType(TestCase):

    def test_plain_maps_to_text(self):
        assert get_field_type(CaseProperty.DataType.PLAIN) == FIELD_TYPE_TEXT

    def test_date_maps_to_date(self):
        assert get_field_type(CaseProperty.DataType.DATE) == FIELD_TYPE_DATE

    def test_number_maps_to_number(self):
        assert get_field_type(CaseProperty.DataType.NUMBER) == FIELD_TYPE_NUMBER

    def test_select_maps_to_select(self):
        assert get_field_type(CaseProperty.DataType.SELECT) == FIELD_TYPE_SELECT

    def test_gps_maps_to_geopoint(self):
        assert get_field_type(CaseProperty.DataType.GPS) == FIELD_TYPE_GEOPOINT

    def test_password_returns_none(self):
        assert get_field_type(CaseProperty.DataType.PASSWORD) is None

    def test_barcode_maps_to_text(self):
        assert get_field_type(CaseProperty.DataType.BARCODE) == FIELD_TYPE_TEXT

    def test_phone_number_maps_to_text(self):
        assert get_field_type(CaseProperty.DataType.PHONE_NUMBER) == FIELD_TYPE_TEXT

    def test_undefined_maps_to_text(self):
        assert get_field_type(CaseProperty.DataType.UNDEFINED) == FIELD_TYPE_TEXT


class TestGetOperationsForFieldType(TestCase):

    def test_text_operations(self):
        ops = get_operations_for_field_type(FIELD_TYPE_TEXT)
        assert 'exact_match' in ops
        assert 'fuzzy_match' in ops
        assert 'is_empty' in ops
        assert 'gt' not in ops

    def test_number_operations(self):
        ops = get_operations_for_field_type(FIELD_TYPE_NUMBER)
        assert 'equals' in ops
        assert 'gt' in ops
        assert 'lte' in ops
        assert 'fuzzy_match' not in ops

    def test_date_operations(self):
        ops = get_operations_for_field_type(FIELD_TYPE_DATE)
        assert 'before' in ops
        assert 'after' in ops
        assert 'date_range' in ops
        assert 'exact_match' not in ops

    def test_select_operations(self):
        ops = get_operations_for_field_type(FIELD_TYPE_SELECT)
        assert 'selected_any' in ops
        assert 'selected_all' in ops
        assert 'exact_match' in ops


class TestGetCapability(TestCase):

    def setUp(self):
        self.case_type = CaseType.objects.create(
            domain='test-domain',
            name='patient',
        )
        self.prop_name = CaseProperty.objects.create(
            case_type=self.case_type,
            name='first_name',
            data_type=CaseProperty.DataType.PLAIN,
        )
        self.prop_dob = CaseProperty.objects.create(
            case_type=self.case_type,
            name='dob',
            data_type=CaseProperty.DataType.DATE,
        )
        self.prop_status = CaseProperty.objects.create(
            case_type=self.case_type,
            name='status',
            data_type=CaseProperty.DataType.SELECT,
        )
        CasePropertyAllowedValue.objects.create(
            case_property=self.prop_status,
            allowed_value='active',
        )
        CasePropertyAllowedValue.objects.create(
            case_property=self.prop_status,
            allowed_value='closed',
        )

    def test_returns_case_types_with_fields(self):
        cap = get_capability('test-domain')
        assert len(cap['case_types']) == 1
        ct = cap['case_types'][0]
        assert ct['name'] == 'patient'
        field_names = [f['name'] for f in ct['fields']]
        assert 'first_name' in field_names
        assert 'dob' in field_names

    def test_field_has_operations(self):
        cap = get_capability('test-domain')
        ct = cap['case_types'][0]
        name_field = next(f for f in ct['fields'] if f['name'] == 'first_name')
        assert 'exact_match' in name_field['operations']

    def test_select_field_has_options(self):
        cap = get_capability('test-domain')
        ct = cap['case_types'][0]
        status_field = next(f for f in ct['fields'] if f['name'] == 'status')
        assert set(status_field['options']) == {'active', 'closed'}

    def test_excludes_deprecated_case_types(self):
        CaseType.objects.create(
            domain='test-domain',
            name='old_type',
            is_deprecated=True,
        )
        cap = get_capability('test-domain')
        names = [ct['name'] for ct in cap['case_types']]
        assert 'old_type' not in names

    def test_excludes_deprecated_properties(self):
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='legacy_prop',
            data_type=CaseProperty.DataType.PLAIN,
            deprecated=True,
        )
        cap = get_capability('test-domain')
        ct = cap['case_types'][0]
        field_names = [f['name'] for f in ct['fields']]
        assert 'legacy_prop' not in field_names

    def test_excludes_password_fields(self):
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='secret',
            data_type=CaseProperty.DataType.PASSWORD,
        )
        cap = get_capability('test-domain')
        ct = cap['case_types'][0]
        field_names = [f['name'] for f in ct['fields']]
        assert 'secret' not in field_names

    def test_auto_values_present(self):
        cap = get_capability('test-domain')
        assert FIELD_TYPE_DATE in cap['auto_values']
        assert FIELD_TYPE_TEXT in cap['auto_values']

    def test_component_input_schemas_present(self):
        cap = get_capability('test-domain')
        assert 'component_input_schemas' in cap
        assert 'exact_match' in cap['component_input_schemas']
