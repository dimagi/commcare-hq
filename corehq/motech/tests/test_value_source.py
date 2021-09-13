import doctest
from datetime import datetime, timedelta
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

import attr
from schema import Use

import corehq.motech.value_source
from corehq.form_processor.models import CommCareCaseIndexSQL, CommCareCaseSQL
from corehq.form_processor.tests.utils import (
    create_case,
    create_case_with_index,
    delete_all_xforms_and_cases,
    sharded,
)
from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DECIMAL,
    COMMCARE_DATA_TYPE_INTEGER,
    COMMCARE_DATA_TYPE_TEXT,
    DIRECTION_BOTH,
    DIRECTION_EXPORT,
    DIRECTION_IMPORT,
)
from corehq.motech.exceptions import JsonpathError
from corehq.motech.value_source import (
    CaseOwnerAncestorLocationField,
    CaseProperty,
    CasePropertyConstantValue,
    CaseTriggerInfo,
    ConstantValue,
    FormUserAncestorLocationField,
    SubcaseValueSource,
    SupercaseValueSource,
    ValueSource,
    as_value_source,
    get_case_trigger_info_for_case,
    get_form_question_values,
)


class GetFormQuestionValuesTests(SimpleTestCase):

    def test_unicode_answer(self):
        value = get_form_question_values({'form': {'foo': {'bar': 'b\u0105z'}}})
        self.assertEqual(value, {'/data/foo/bar': 'b\u0105z'})

    def test_unicode_question(self):
        value = get_form_question_values({'form': {'foo': {'b\u0105r': 'baz'}}})
        self.assertEqual(value, {'/data/foo/b\u0105r': 'baz'})

    def test_received_on(self):
        value = get_form_question_values({
            'form': {
                'foo': {'bar': 'baz'},
            },
            'received_on': '2018-11-06T18:30:00.000000Z',
        })
        self.assertDictEqual(value, {
            '/data/foo/bar': 'baz',
            '/metadata/received_on': '2018-11-06T18:30:00.000000Z',
        })

    def test_metadata(self):
        value = get_form_question_values({
            'form': {
                '@xmlns': 'http://openrosa.org/formdesigner/04279622',
                'foo': {'bar': 'baz'},
                'meta': {
                    'timeStart': '2018-11-06T18:00:00.000000Z',
                    'timeEnd': '2018-11-06T18:15:00.000000Z',
                    'spam': 'ham',
                },
            },
            'received_on': '2018-11-06T18:30:00.000000Z',
        })
        self.assertDictEqual(value, {
            '/data/foo/bar': 'baz',
            '/metadata/xmlns': 'http://openrosa.org/formdesigner/04279622',
            '/metadata/timeStart': '2018-11-06T18:00:00.000000Z',
            '/metadata/timeEnd': '2018-11-06T18:15:00.000000Z',
            '/metadata/spam': 'ham',
            '/metadata/received_on': '2018-11-06T18:30:00.000000Z',
        })


class CaseTriggerInfoTests(SimpleTestCase):

    def test_default_attr(self):
        info = CaseTriggerInfo(
            domain="test-domain",
            case_id='c0ffee',
        )
        self.assertIsNone(info.name)

    def test_factory_attr(self):
        info = CaseTriggerInfo(
            domain="test-domain",
            case_id='c0ffee',
        )
        self.assertEqual(info.form_question_values, {})

    def test_required_attr(self):
        with self.assertRaises(TypeError):
            CaseTriggerInfo(
                domain="test-domain",
            )


class CasePropertyValidationTests(SimpleTestCase):

    def test_valid_case_property(self):
        case_property = as_value_source({"case_property": "foo"})
        self.assertIsInstance(case_property, CaseProperty)
        self.assertEqual(case_property.case_property, "foo")

    def test_blank_case_property(self):
        with self.assertRaisesRegex(TypeError, "Unable to determine class for {'case_property': ''}"):
            as_value_source({"case_property": ""})

    def test_missing_case_property(self):
        with self.assertRaisesRegex(TypeError, "Unable to determine class for {}"):
            as_value_source({})

    def test_null_case_property(self):
        with self.assertRaisesRegex(TypeError, "Unable to determine class for {'case_property': None}"):
            as_value_source({"case_property": None})

    def test_doc_type(self):
        case_property = as_value_source({
            "doc_type": "CaseProperty",
            "case_property": "foo",
        })
        self.assertIsInstance(case_property, CaseProperty)
        self.assertEqual(case_property.case_property, "foo")
        with self.assertRaises(AttributeError):
            case_property.doc_type


class ConstantValueTests(SimpleTestCase):

    def test_get_commcare_value(self):
        """
        get_commcare_value() should convert from value data type to
        CommCare data type
        """
        one = as_value_source({
            "value": 1.0,
            "value_data_type": COMMCARE_DATA_TYPE_DECIMAL,
            "commcare_data_type": COMMCARE_DATA_TYPE_INTEGER,
            "external_data_type": COMMCARE_DATA_TYPE_TEXT,
        })
        self.assertEqual(one.get_commcare_value('foo'), 1)

    def test_serialize(self):
        """
        serialize() should convert from CommCare data type to external
        data type
        """
        one = as_value_source({
            "value": 1.0,
            "value_data_type": COMMCARE_DATA_TYPE_DECIMAL,
            "commcare_data_type": COMMCARE_DATA_TYPE_INTEGER,
            "external_data_type": COMMCARE_DATA_TYPE_TEXT,
        })
        self.assertEqual(one.serialize(1), '1')

    def test_deserialize(self):
        """
        deserialize() should convert from external data type to CommCare
        data type
        """
        one = as_value_source({
            "value": 1.0,
            "value_data_type": COMMCARE_DATA_TYPE_DECIMAL,
            "commcare_data_type": COMMCARE_DATA_TYPE_TEXT,
            "external_data_type": COMMCARE_DATA_TYPE_INTEGER,
        })
        self.assertEqual(one.deserialize("foo"), '1')


class JsonPathCasePropertyTests(SimpleTestCase):

    def test_blank_path(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = as_value_source({
            "case_property": "bar",
            "jsonpath": "",
        })
        with self.assertRaises(JsonpathError):
            value_source.get_import_value(json_doc)

    def test_no_values(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = as_value_source({
            "case_property": "bar",
            "jsonpath": "foo.qux",
        })
        external_value = value_source.get_import_value(json_doc)
        self.assertIsNone(external_value)

    def test_one_value(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = as_value_source({
            "case_property": "bar",
            "jsonpath": "foo.bar",
        })
        external_value = value_source.get_import_value(json_doc)
        self.assertEqual(external_value, "baz")

    def test_many_values(self):
        json_doc = {"foo": [{"bar": "baz"}, {"bar": "qux"}]}
        value_source = as_value_source({
            "case_property": "bar",
            "jsonpath": "foo[*].bar",
        })
        external_value = value_source.get_import_value(json_doc)
        self.assertEqual(external_value, ["baz", "qux"])


class CasePropertyConstantValueTests(SimpleTestCase):

    def test_one_value(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = as_value_source({
            "case_property": "baz",
            "value": "qux",
            "jsonpath": "foo.bar",
        })
        external_value = value_source.get_import_value(json_doc)
        self.assertEqual(external_value, "qux")


class DirectionTests(SimpleTestCase):

    def test_direction_in_true(self):
        value_source = ValueSource(direction=DIRECTION_IMPORT)
        self.assertTrue(value_source.can_import)

    def test_direction_in_false(self):
        value_source = ValueSource(direction=DIRECTION_IMPORT)
        self.assertFalse(value_source.can_export)

    def test_direction_out_true(self):
        value_source = ValueSource(direction=DIRECTION_EXPORT)
        self.assertTrue(value_source.can_export)

    def test_direction_out_false(self):
        value_source = ValueSource(direction=DIRECTION_EXPORT)
        self.assertFalse(value_source.can_import)

    def test_direction_both_true(self):
        value_source = ValueSource(direction=DIRECTION_BOTH)
        self.assertTrue(value_source.can_import)
        self.assertTrue(value_source.can_export)


class TestAsValueSourceSchema(SimpleTestCase):

    def test_as_constant_value(self):
        value_source = as_value_source({
            "value": "spam",
        })
        self.assertIsInstance(value_source, ConstantValue)

    def test_as_case_property_constant_value(self):
        value_source = as_value_source({
            "value": "spam",
            "case_property": "spam",
        })
        self.assertIsInstance(value_source, CasePropertyConstantValue)

    def test_type_error(self):
        with self.assertRaises(TypeError):
            as_value_source({})


class FormUserAncestorLocationFieldTests(SimpleTestCase):

    def test_with_form_user_ancestor_location_field(self):
        json_object = as_value_source({"form_user_ancestor_location_field": "dhis_id"})
        self.assertIsInstance(json_object, FormUserAncestorLocationField)
        self.assertEqual(json_object.form_user_ancestor_location_field, "dhis_id")

    def test_with_form_user_ancestor_location_field_doc_type(self):
        json_object = as_value_source({
            "doc_type": "FormUserAncestorLocationField",
            "form_user_ancestor_location_field": "dhis_id",
        })
        self.assertIsInstance(json_object, FormUserAncestorLocationField)
        self.assertEqual(json_object.form_user_ancestor_location_field, "dhis_id")

    def test_with_location_field_doc_type(self):
        json_object = as_value_source({
            "doc_type": "FormUserAncestorLocationField",
            "location_field": "dhis_id",
        })
        self.assertIsInstance(json_object, FormUserAncestorLocationField)
        self.assertEqual(json_object.form_user_ancestor_location_field, "dhis_id")

    def test_with_location(self):
        with self.assertRaises(TypeError):
            as_value_source({"location_field": "dhis_id"})


class CaseOwnerAncestorLocationFieldTests(SimpleTestCase):

    def test_with_form_user_ancestor_location_field(self):
        json_object = as_value_source({"case_owner_ancestor_location_field": "dhis_id"})
        self.assertIsInstance(json_object, CaseOwnerAncestorLocationField)
        self.assertEqual(json_object.case_owner_ancestor_location_field, "dhis_id")

    def test_with_form_user_ancestor_location_field_doc_type(self):
        json_object = as_value_source({
            "doc_type": "CaseOwnerAncestorLocationField",
            "case_owner_ancestor_location_field": "dhis_id",
        })
        self.assertIsInstance(json_object, CaseOwnerAncestorLocationField)
        self.assertEqual(json_object.case_owner_ancestor_location_field, "dhis_id")

    def test_with_location_field_doc_type(self):
        json_object = as_value_source({
            "doc_type": "CaseOwnerAncestorLocationField",
            "location_field": "dhis_id",
        })
        self.assertIsInstance(json_object, CaseOwnerAncestorLocationField)
        self.assertEqual(json_object.case_owner_ancestor_location_field, "dhis_id")

    def test_with_location(self):
        with self.assertRaises(TypeError):
            as_value_source({"location_field": "dhis_id"})


class TestSupercaseValueSourceValidation(SimpleTestCase):

    def test_supercase_value_source(self):
        value_source = as_value_source({
            'supercase_value_source': {'case_property': 'foo'},
        })
        self.assertIsInstance(value_source, SupercaseValueSource)

    def test_identifier(self):
        value_source = as_value_source({
            'supercase_value_source': {'case_property': 'foo'},
            'identifier': 'bar',
        })
        self.assertIsInstance(value_source, SupercaseValueSource)

    def test_referenced_type(self):
        value_source = as_value_source({
            'supercase_value_source': {'case_property': 'foo'},
            'referenced_type': 'bar',
        })
        self.assertIsInstance(value_source, SupercaseValueSource)

    def test_relationship(self):
        value_source = as_value_source({
            'supercase_value_source': {'case_property': 'foo'},
            'relationship': 'extension',
        })
        self.assertIsInstance(value_source, SupercaseValueSource)

    def test_relationship_invalid(self):
        with self.assertRaises(TypeError):
            as_value_source({
                'supercase_value_source': {'case_property': 'foo'},
                'relationship': 'invalid',
            })

    def test_supercase_value_source_empty(self):
        with self.assertRaises(TypeError):
            as_value_source({
                'supercase_value_source': {},
            })


class TestSubcaseValueSourceValidation(SimpleTestCase):

    def test_subcase_value_source(self):
        value_source = as_value_source({
            'subcase_value_source': {'case_property': 'foo'},
        })
        self.assertIsInstance(value_source, SubcaseValueSource)

    def test_case_types(self):
        value_source = as_value_source({
            'subcase_value_source': {'case_property': 'foo'},
            'case_types': ['bar'],
        })
        self.assertIsInstance(value_source, SubcaseValueSource)

    def test_is_closed(self):
        value_source = as_value_source({
            'subcase_value_source': {'case_property': 'foo'},
            'is_closed': False,
        })
        self.assertIsInstance(value_source, SubcaseValueSource)

    def test_subcase_value_source_empty(self):
        with self.assertRaises(TypeError):
            as_value_source({
                'subcase_value_source': {},
            })


class AsValueSourceTests(SimpleTestCase):

    def test_as_value_source(self):

        @attr.s(auto_attribs=True, kw_only=True)
        class StringValueSource(ValueSource):
            test_value: str

            @classmethod
            def get_schema_params(cls):
                (schema, *other_args), kwargs = super().get_schema_params()
                schema.update({"test_value": Use(str)})  # Casts value as string
                return (schema, *other_args), kwargs

        data = {"test_value": 10}
        value_source = as_value_source(data)
        self.assertEqual(data, {"test_value": 10})
        self.assertIsInstance(value_source, StringValueSource)
        self.assertEqual(value_source.test_value, "10")


@sharded
class TestSubcaseValueSourceSetExternalValue(TestCase):

    domain = 'lincoln-montana'

    def setUp(self):
        now = datetime.utcnow()
        case_kwargs = {
            'owner_id': uuid4().hex,
            'modified_on': now,
            'server_modified_on': now,
        }
        self.host_case_id = uuid4().hex
        case = CommCareCaseSQL(
            case_id=self.host_case_id,
            domain=self.domain,
            type='person',
            name='Ted',
            **case_kwargs,
        )
        self.host_case = create_case(case)

        case = CommCareCaseSQL(
            case_id=uuid4().hex,
            domain=self.domain,
            type='person_name',
            name='Theodore',
            case_json={
                'given_names': 'Theodore John',
                'family_name': 'Kaczynski',
            },
            **case_kwargs,
        )
        index = CommCareCaseIndexSQL(
            domain=self.domain,
            identifier='host',
            referenced_type='person',
            referenced_id=self.host_case_id,
            relationship_id=CommCareCaseIndexSQL.EXTENSION,
        )
        self.ext_case_1 = create_case_with_index(case, index)

        case = CommCareCaseSQL(
            case_id=uuid4().hex,
            domain=self.domain,
            type='person_name',
            name='Unabomber',
            case_json={
                'given_names': 'Unabomber',
            },
            **case_kwargs,
        )
        index = CommCareCaseIndexSQL(
            domain=self.domain,
            identifier='host',
            referenced_type='person',
            referenced_id=self.host_case_id,
            relationship_id=CommCareCaseIndexSQL.EXTENSION,
        )
        self.ext_case_2 = create_case_with_index(case, index)

    def tearDown(self):
        delete_all_xforms_and_cases(self.domain)

    def test_set_external_data(self):
        value_source_configs = [{
            'case_property': 'name',
            'jsonpath': '$.name[0].text',
        }, {
            'subcase_value_source': {
                'case_property': 'given_names',
                # Use counter1 to skip the name set by the parent case
                'jsonpath': '$.name[{counter1}].given[0]',
            },
            'case_types': ['person_name'],
        }, {
            'subcase_value_source': {
                'case_property': 'family_name',
                'jsonpath': '$.name[{counter1}].family',
            },
            'case_types': ['person_name'],
        }]

        external_data = {}
        case_trigger_info = get_case_trigger_info_for_case(
            self.host_case,
            value_source_configs,
        )
        for value_source_config in value_source_configs:
            value_source = as_value_source(value_source_config)
            value_source.set_external_value(external_data, case_trigger_info)

        name = external_data['name']
        self.assertIn({'text': 'Ted'}, name)
        self.assertIn({'given': ['Theodore John'], 'family': 'Kaczynski'}, name)
        self.assertIn({'given': ['Unabomber']}, name)


@sharded
class TestSupercaseValueSourceSetExternalValue(TestCase):

    domain = 'quarantinewhile'

    def setUp(self):
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        owner_id = uuid4().hex
        self.parent_case_id = uuid4().hex
        case = CommCareCaseSQL(
            case_id=self.parent_case_id,
            domain=self.domain,
            type='person',
            name='Joe',
            owner_id=owner_id,
            modified_on=yesterday,
            server_modified_on=yesterday,
        )
        self.parent_case = create_case(case)

        case = CommCareCaseSQL(
            case_id=uuid4().hex,
            domain=self.domain,
            type='temperature',
            case_json={
                'value': '36.2',
            },
            owner_id=owner_id,
            modified_on=yesterday,
            server_modified_on=yesterday,
        )
        index = CommCareCaseIndexSQL(
            domain=self.domain,
            identifier='parent',
            referenced_type='person',
            referenced_id=self.parent_case_id,
            relationship_id=CommCareCaseIndexSQL.CHILD,
        )
        self.child_case_1 = create_case_with_index(case, index)

        case = CommCareCaseSQL(
            case_id=uuid4().hex,
            domain=self.domain,
            type='temperature',
            case_json={
                'value': '36.6',
            },
            owner_id=owner_id,
            modified_on=now,
            server_modified_on=now,
        )
        index = CommCareCaseIndexSQL(
            domain=self.domain,
            identifier='parent',
            referenced_type='person',
            referenced_id=self.parent_case_id,
            relationship_id=CommCareCaseIndexSQL.CHILD,
        )
        self.child_case_2 = create_case_with_index(case, index)

    def tearDown(self):
        delete_all_xforms_and_cases(self.domain)

    def test_set_external_data(self):
        value_source_configs = [{
            'case_property': 'value',
            'jsonpath': '$.valueQuantity.value',
            'external_data_type': COMMCARE_DATA_TYPE_DECIMAL,
        }, {
            'value': 'degrees Celsius',
            'jsonpath': '$.valueQuantity.unit',
        }, {
            'supercase_value_source': {
                'case_property': 'case_id',
                'jsonpath': '$.subject.reference',
            },
            'identifier': 'parent',
            'referenced_type': 'person',
        }, {
            'supercase_value_source': {
                'case_property': 'name',
                'jsonpath': '$.subject.display',
            },
            'identifier': 'parent',
            'referenced_type': 'person',
        }]

        resources = []
        for case in (self.child_case_1, self.child_case_2):
            external_data = {}
            info = get_case_trigger_info_for_case(case, value_source_configs)
            for value_source_config in value_source_configs:
                value_source = as_value_source(value_source_config)
                value_source.set_external_value(external_data, info)
            resources.append(external_data)

        self.assertEqual(resources, [{
            'subject': {
                'reference': self.parent_case_id,
                'display': 'Joe',
            },
            'valueQuantity': {
                'value': 36.2,  # case 1
                'unit': 'degrees Celsius',
            },
        }, {
            'subject': {
                'reference': self.parent_case_id,
                'display': 'Joe',
            },
            'valueQuantity': {
                'value': 36.6,  # case 2
                'unit': 'degrees Celsius',
            },
        }])


def test_doctests():
    results = doctest.testmod(corehq.motech.value_source, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
