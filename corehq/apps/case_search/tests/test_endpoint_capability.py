from django.test import TestCase

from corehq.apps.case_search.endpoint_capability import (
    COMPONENT_INPUT_SCHEMAS,
    DATATYPE_TO_FIELD_TYPE,
    OPERATIONS_BY_FIELD_TYPE,
    get_capability,
)
from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyAllowedValue,
    CaseType,
)

DOMAIN = 'test-domain'


class TestDataTypeMappings(TestCase):

    def test_password_excluded(self):
        self.assertNotIn(CaseProperty.DataType.PASSWORD, DATATYPE_TO_FIELD_TYPE)

    def test_all_non_password_types_mapped(self):
        for dt in CaseProperty.DataType:
            if dt == CaseProperty.DataType.PASSWORD:
                continue
            self.assertIn(dt, DATATYPE_TO_FIELD_TYPE, f'{dt} not in DATATYPE_TO_FIELD_TYPE')

    def test_text_operations_present(self):
        ops = OPERATIONS_BY_FIELD_TYPE['text']
        self.assertIn('exact_match', ops)
        self.assertIn('fuzzy_match', ops)
        self.assertIn('is_empty', ops)

    def test_number_operations_present(self):
        ops = OPERATIONS_BY_FIELD_TYPE['number']
        self.assertIn('gt', ops)
        self.assertIn('lte', ops)

    def test_date_operations_present(self):
        ops = OPERATIONS_BY_FIELD_TYPE['date']
        self.assertIn('date_range', ops)
        self.assertIn('before', ops)

    def test_select_operations_present(self):
        ops = OPERATIONS_BY_FIELD_TYPE['select']
        self.assertIn('selected_any', ops)
        self.assertIn('selected_all', ops)

    def test_date_range_has_two_slots(self):
        slots = COMPONENT_INPUT_SCHEMAS['date_range']
        self.assertEqual(len(slots), 2)
        names = {s['name'] for s in slots}
        self.assertEqual(names, {'start', 'end'})

    def test_is_empty_has_no_slots(self):
        self.assertEqual(COMPONENT_INPUT_SCHEMAS['is_empty'], [])

    def test_all_operations_have_schemas(self):
        all_ops = set()
        for ops in OPERATIONS_BY_FIELD_TYPE.values():
            all_ops.update(ops)
        for op in all_ops:
            self.assertIn(op, COMPONENT_INPUT_SCHEMAS, f'{op} missing from COMPONENT_INPUT_SCHEMAS')


class TestGetCapability(TestCase):

    def setUp(self):
        self.case_type = CaseType.objects.create(
            domain=DOMAIN, name='patient',
        )

    def test_empty_domain(self):
        result = get_capability('empty-domain')
        self.assertEqual(result['case_types'], [])

    def test_case_type_with_fields(self):
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='first_name',
            data_type=CaseProperty.DataType.PLAIN,
        )
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='dob',
            data_type=CaseProperty.DataType.DATE,
        )
        result = get_capability(DOMAIN)
        self.assertEqual(len(result['case_types']), 1)
        ct = result['case_types'][0]
        self.assertEqual(ct['name'], 'patient')
        self.assertEqual(len(ct['fields']), 2)
        field_names = {f['name'] for f in ct['fields']}
        self.assertEqual(field_names, {'first_name', 'dob'})

    def test_field_type_mapping(self):
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='age',
            data_type=CaseProperty.DataType.NUMBER,
        )
        result = get_capability(DOMAIN)
        field = result['case_types'][0]['fields'][0]
        self.assertEqual(field['type'], 'number')
        self.assertEqual(field['operations'], OPERATIONS_BY_FIELD_TYPE['number'])

    def test_password_fields_excluded(self):
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='pin',
            data_type=CaseProperty.DataType.PASSWORD,
        )
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='first_name',
            data_type=CaseProperty.DataType.PLAIN,
        )
        result = get_capability(DOMAIN)
        field_names = {f['name'] for f in result['case_types'][0]['fields']}
        self.assertNotIn('pin', field_names)
        self.assertIn('first_name', field_names)

    def test_deprecated_case_types_excluded(self):
        CaseType.objects.create(
            domain=DOMAIN, name='old_type', is_deprecated=True,
        )
        result = get_capability(DOMAIN)
        ct_names = {ct['name'] for ct in result['case_types']}
        self.assertNotIn('old_type', ct_names)

    def test_deprecated_properties_excluded(self):
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='old_prop',
            data_type=CaseProperty.DataType.PLAIN,
            deprecated=True,
        )
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='active_prop',
            data_type=CaseProperty.DataType.PLAIN,
        )
        result = get_capability(DOMAIN)
        field_names = {f['name'] for f in result['case_types'][0]['fields']}
        self.assertNotIn('old_prop', field_names)
        self.assertIn('active_prop', field_names)

    def test_select_field_includes_options(self):
        prop = CaseProperty.objects.create(
            case_type=self.case_type,
            name='status',
            data_type=CaseProperty.DataType.SELECT,
        )
        CasePropertyAllowedValue.objects.create(
            case_property=prop, allowed_value='active',
        )
        CasePropertyAllowedValue.objects.create(
            case_property=prop, allowed_value='closed',
        )
        result = get_capability(DOMAIN)
        field = result['case_types'][0]['fields'][0]
        self.assertEqual(field['type'], 'select')
        self.assertIn('options', field)
        self.assertEqual(set(field['options']), {'active', 'closed'})

    def test_non_select_field_has_no_options(self):
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='first_name',
            data_type=CaseProperty.DataType.PLAIN,
        )
        result = get_capability(DOMAIN)
        field = result['case_types'][0]['fields'][0]
        self.assertNotIn('options', field)

    def test_auto_values_included(self):
        result = get_capability(DOMAIN)
        self.assertIn('auto_values', result)
        self.assertIn('date', result['auto_values'])
        self.assertIn('text', result['auto_values'])

    def test_component_schemas_included(self):
        result = get_capability(DOMAIN)
        self.assertIn('component_schemas', result)
        self.assertIn('date_range', result['component_schemas'])
        self.assertEqual(len(result['component_schemas']['date_range']), 2)

    def test_undefined_type_maps_to_text(self):
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='misc',
            data_type=CaseProperty.DataType.UNDEFINED,
        )
        result = get_capability(DOMAIN)
        field = result['case_types'][0]['fields'][0]
        self.assertEqual(field['type'], 'text')
