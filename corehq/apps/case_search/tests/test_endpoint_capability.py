from django.test import SimpleTestCase, TestCase

from corehq.apps.case_search.endpoint_capability import (
    COMPONENT_INPUT_SCHEMAS,
    _AUTO_VALUES,
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


class TestComponentInputSchemas(SimpleTestCase):

    def test_all_values_are_lists(self):
        for op, schema in COMPONENT_INPUT_SCHEMAS.items():
            assert isinstance(schema, list), f"{op}: expected list, got {type(schema)}"

    def test_all_items_have_name_and_type_strings(self):
        for op, schema in COMPONENT_INPUT_SCHEMAS.items():
            for item in schema:
                assert isinstance(item.get('name'), str), f"{op}: item 'name' must be str"
                assert isinstance(item.get('type'), str), f"{op}: item 'type' must be str"


class TestAutoValues(SimpleTestCase):

    def test_all_values_are_lists(self):
        for field_type, values in _AUTO_VALUES.items():
            assert isinstance(values, list), f"{field_type}: expected list, got {type(values)}"

    def test_all_items_have_ref_and_label_strings(self):
        for field_type, values in _AUTO_VALUES.items():
            for item in values:
                assert isinstance(item.get('ref'), str), f"{field_type}: item 'ref' must be str"
                assert isinstance(item.get('label'), str), f"{field_type}: item 'label' must be str"


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
