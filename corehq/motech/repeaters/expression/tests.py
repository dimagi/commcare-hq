import dataclasses
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.mock import CaseFactory
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.userreports.models import UCRExpression
from corehq.form_processor.models import CommCareCase
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.expression.repeaters import (
    CaseExpressionRepeater,
    ArcGISFormExpressionRepeater,
    FormExpressionRepeater,
)
from corehq.motech.repeaters.models import RepeatRecord
from corehq.util.test_utils import flag_enabled


@dataclasses.dataclass
class MockResponse:
    status_code: int
    text: str = ""
    headers: dict = dataclasses.field(default_factory=dict)
    reason: str = "success"

    def json(self):
        return json.loads(self.text)


class BaseExpressionRepeaterTest(TestCase, DomainSubscriptionMixin):
    xmlns = 'http://foo.org/bar/123'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'test'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(clear_plan_version_cache)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.setup_subscription(cls.domain, SoftwarePlanEdition.PRO)
        cls.addClassCleanup(cls.teardown_subscriptions)

        cls.factory = CaseFactory(cls.domain)

        url = 'fake-url'
        cls.connection = ConnectionSettings.objects.create(domain=cls.domain, name=url, url=url)

    def setUp(self):
        self._create_repeater()

    def _create_repeater(self):
        pass

    @classmethod
    def repeat_records(cls, domain_name):
        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        return RepeatRecord.objects.filter(domain=domain_name, next_check__lt=later)

    def _create_case_block(self, case_id):
        return CaseBlock(
            create=True,
            case_id=case_id,
            case_type='person',
            case_name=uuid.uuid4().hex,
        ).as_text()

    def _create_case(self, xmlns):
        return self.factory.post_case_blocks(
            [self._create_case_block(uuid.uuid4().hex)],
            xmlns=xmlns,
        )[0]


@flag_enabled('EXPRESSION_REPEATER')
class CaseExpressionRepeaterTest(BaseExpressionRepeaterTest):

    def _create_repeater(self):
        self.repeater = CaseExpressionRepeater(
            domain=self.domain,
            connection_settings_id=self.connection.id,
            configured_filter={
                "type": "or",
                "filters": [
                    {
                        "type": "boolean_expression",
                        "expression": {
                            "type": "reduce_items",
                            "aggregation_fn": "count",
                            "items_expression": {
                                "type": "get_case_forms",
                                "case_id_expression": {
                                    "property_name": "case_id",
                                    "type": "property_name"
                                }
                            }
                        },
                        "operator": "gt",
                        "property_value": 1
                    },
                    {
                        "type": "boolean_expression",
                        "expression": {
                            "type": "property_name",
                            "property_name": "type",
                        },
                        "operator": "eq",
                        "property_value": "forward-me",
                    }
                ]
            },
            configured_expression={
                "type": "dict",
                "properties": {
                    "case_id": {
                        "type": "property_name",
                        "property_name": "case_id",
                    },
                    "a-constant": {
                        "type": "constant",
                        "constant": "foo",
                    }
                }
            }
        )
        self.repeater.save()

    def test_filter_cases(self):
        forwardable_case = self.factory.create_case(case_type='forward-me')
        unforwardable_case = self.factory.create_case(case_type='dont-forward-me')
        repeat_records = self.repeat_records(self.domain).all()
        self.assertEqual(RepeatRecord.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(repeat_records[0].payload_id, forwardable_case.case_id)

        self.factory.update_case(unforwardable_case.case_id, update={'now-this-case': 'can-be-forwarded'})
        repeat_records = self.repeat_records(self.domain).all()
        self.assertEqual(RepeatRecord.objects.filter(domain=self.domain).count(), 2)
        self.assertEqual(repeat_records[1].payload_id, unforwardable_case.case_id)

    def test_payload(self):
        forwardable_case = self.factory.create_case(case_type='forward-me')
        repeat_record = self.repeat_records(self.domain).all()[0]
        self.assertEqual(repeat_record.get_payload(), json.dumps({
            "case_id": forwardable_case.case_id,
            "a-constant": "foo",
        }))

    @flag_enabled("UCR_EXPRESSION_REGISTRY")
    def test_custom_url(self):

        self.repeater.url_template = "/{variable1}/a_thing/delete?case_id={case_id}&{missing_variable}='foo'"

        UCRExpression.objects.create(
            name='variable1',
            domain=self.domain,
            expression_type="named_expression",
            definition={
                "type": "property_name",
                "property_name": "prop1"
            },
        )
        UCRExpression.objects.create(
            name='case_id',
            domain=self.domain,
            expression_type="named_expression",
            definition={
                "type": "property_name",
                "property_name": "case_id"
            },
        )

        forwardable_case = self.factory.create_case(case_type='forward-me', update={'prop1': 'foo'})
        repeat_record = self.repeat_records(self.domain).all()[0]

        expected_url = self.connection.url + f"/foo/a_thing/delete?case_id={forwardable_case.case_id}&='foo'"

        self.assertEqual(
            self.repeater.get_url(repeat_record),
            expected_url
        )

    def test_process_response_filter(self):
        self.factory.create_case(case_type='forward-me')
        repeat_record = self.repeat_records(self.domain).all()[0]
        self.repeater.case_action_filter_expression = {
            "type": "boolean_expression",
            "expression": {
                "type": "jsonpath",
                "jsonpath": "response.status_code",
            },
            "operator": "eq",
            "property_value": 201,
        }
        self.repeater._perform_case_update = Mock()
        response = MockResponse(200)
        self.assertFalse(self.repeater._process_response_as_case_update(response, repeat_record))
        self.repeater._perform_case_update.assert_not_called()

        response = MockResponse(201)
        self.assertTrue(self.repeater._process_response_as_case_update(response, repeat_record))
        self.repeater._perform_case_update.assert_called()

    def test_process_response(self):
        self.factory.create_case(case_type='forward-me')
        repeat_record = self.repeat_records(self.domain).all()[0]
        self.repeater.case_action_filter_expression = {
            "type": "boolean_expression",
            "expression": {
                "type": "jsonpath",
                "jsonpath": "response.status_code",
            },
            "operator": "eq",
            "property_value": 200,
        }
        self.repeater.case_action_expression = {
            'type': 'dict',
            'properties': {
                'create': False,
                'case_id': {
                    'type': 'jsonpath',
                    'jsonpath': 'payload.id',
                },
                'properties': {
                    'type': 'dict',
                    'properties': {
                        'type': 'dict',
                        'prop_from_response': {
                            'type': 'jsonpath',
                            'jsonpath': 'response.body.aValue',
                        }
                    }
                }
            }
        }
        response = MockResponse(200, '{"aValue": "aResponseValue"}')
        self.repeater.handle_response(response, repeat_record)
        case = CommCareCase.objects.get_case(repeat_record.payload_id, self.domain)
        self.assertEqual(case.get_case_property('prop_from_response'), 'aResponseValue')

        # case shouldn't be eligible to forward again because it was just updated by the repeater
        self.assertFalse(self.repeater.allowed_to_forward(case))

        # case should be eligible to forward by a different repeater (one with a different id)
        self.repeater.id = "a different repeater"
        self.assertTrue(self.repeater.allowed_to_forward(case))


class FormExpressionRepeaterTest(BaseExpressionRepeaterTest):

    xform_xml_template = """<?xml version='1.0' ?>
        <data xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="{}">

            <meta>
                <n3:location xmlns:n3="http://commcarehq.org/xforms">1.1 2.2 3.3 4.4</n3:location>
                <instanceID>{}</instanceID>
            </meta>
        {}
        </data>
        """

    case_id = uuid.uuid4().hex

    def _create_repeater(self):
        self.repeater = FormExpressionRepeater(
            domain=self.domain,
            connection_settings_id=self.connection.id,
            configured_filter={
                "type": "boolean_expression",
                "expression": {
                    "type": "property_name",
                    "property_name": "xmlns",
                },
                "operator": "eq",
                "property_value": self.xmlns,
            },
            configured_expression={
                "type": "dict",
                "properties": {
                    "case_id": {
                        "type": "property_path",
                        "property_path": ["form", "case", "@case_id"],
                    },
                    "properties": {
                        "type": "dict",
                        "properties": {
                            "meta_gps_point": {
                                "type": "property_path",
                                "property_path": ["form", "meta", "location", "#text"],
                            },
                        },
                    },
                },
            },
        )
        self.repeater.save()

    @property
    def expected_payload(self):
        return json.dumps({
            'case_id': self.case_id,
            'properties': {
                'meta_gps_point': '1.1 2.2 3.3 4.4'
            }
        })

    def test_filter_forms(self):
        forwardable_form = self._create_case(self.xmlns)
        self._create_case(xmlns='http://do-not.org/forward')
        self.assertEqual(RepeatRecord.objects.filter(domain=self.domain).count(), 1)
        repeat_records = self.repeat_records(self.domain).all()
        self.assertEqual(repeat_records[0].payload_id, forwardable_form.form_id)

    def test_payload(self):
        instance_id = uuid.uuid4().hex
        xform_xml = self.xform_xml_template.format(
            self.xmlns,
            instance_id,
            self._create_case_block(self.case_id),
        )
        submit_form_locally(xform_xml, self.domain)
        repeat_record = self.repeat_records(self.domain).all()[0]
        self.assertEqual(repeat_record.get_payload(), self.expected_payload)


class ArcGISExpressionRepeaterTest(FormExpressionRepeaterTest):

    xform_xml_template = """<?xml version='1.0' ?>
        <data xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="{}">
            <person_name>Timmy</person_name>
            <gps_coordinate>1.1 2.2</gps_coordinate>
            <meta>
                <deviceID>O2XLT0WZW97W1A91E2W1Y0NJG</deviceID>
                <timeStart>2011-10-01T15:25:18.404-04</timeStart>
                <timeEnd>2011-10-01T15:26:29.551-04</timeEnd>
                <username>admin</username>
                <userID>1234</userID>
                <instanceID>{}</instanceID>
            </meta>
        {}
        </data>
        """

    def _create_repeater(self):
        self.repeater = ArcGISFormExpressionRepeater(
            domain=self.domain,
            connection_settings_id=self.connection.id,
            configured_filter={
                "type": "boolean_expression",
                "expression": {
                    "type": "property_name",
                    "property_name": "xmlns",
                },
                "operator": "eq",
                "property_value": self.xmlns,
            },
            configured_expression={
                "type": "dict",
                "properties": {
                    "attributes": {
                        "type": "dict",
                        "properties": {
                            "name": {
                                "type": "property_path",
                                "property_path": ["form", "person_name"],
                            },
                        },
                    },
                    "geometry": {
                        "type": "dict",
                        "properties": {
                            "x": {
                                "datatype": "decimal",
                                "type": "split_string",
                                "string_expression": {
                                    "type": "property_path",
                                    "property_path": ["form", "gps_coordinate"],
                                },
                                "index_expression": {"type": "constant", "constant": 1},
                            },
                            "y": {
                                "datatype": "decimal",
                                "type": "split_string",
                                "string_expression": {
                                    "type": "property_path",
                                    "property_path": ["form", "gps_coordinate"],
                                },
                                "index_expression": {"type": "constant", "constant": 0},
                            },
                            "spatialReference": {
                                "type": "dict",
                                "properties": {
                                    "wkid": {"type": "constant", "constant": 4326}
                                },
                            },
                        },
                    },
                },
            },
        )
        self.repeater.save()

    @property
    def expected_payload(self):
        return {
            'features': json.dumps([{
                'attributes': {
                    'name': 'Timmy',
                },
                'geometry': {
                    'x': '2.2',
                    'y': '1.1',
                    'spatialReference': {
                        'wkid': 4326
                    }
                }
            }]),
            'f': 'json',
            'token': ''
        }
