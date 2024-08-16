import dataclasses
from datetime import datetime

from django.test import SimpleTestCase, TestCase

from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION, UCR_NAMED_FILTER
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import UCRExpression
from corehq.motech.generic_inbound.backend.base import (
    _apply_api_filter,
    _execute_generic_api,
    _validate_api_request,
)
from corehq.motech.generic_inbound.exceptions import (
    GenericInboundRequestFiltered,
    GenericInboundValidationError,
)
from corehq.motech.generic_inbound.models import (
    ConfigurableAPI,
    ConfigurableApiValidation,
)
from corehq.motech.generic_inbound.utils import get_evaluation_context
from corehq.util.test_utils import flag_enabled


@dataclasses.dataclass
class MockUser:
    user_id: str = "123"
    username: str = "integration_user"
    password: str = "sha256:123123"
    date_joined: datetime = dataclasses.field(default_factory=datetime.utcnow)
    user_session_data: dict = dataclasses.field(default_factory=dict)


class TestGenericInboundAPI(SimpleTestCase):
    domain_name = 'ucr-api-test'

    def test_spec_error(self):
        api_model = ConfigurableAPI(
            domain=self.domain_name,
            transform_expression=UCRExpression(definition={})
        )
        # mock 'get_validations' to prevent reverse foreign key lookup on unsaved obj
        api_model.get_validations = lambda: []
        user = MockUser()
        context = get_evaluation_context(user, 'post', {}, {}, {})
        with self.assertRaises(BadSpecError):
            _execute_generic_api(self.domain_name, user, "device_id", context, api_model)

    def test_no_filter(self):
        api_model = ConfigurableAPI(
            domain=self.domain_name,
            transform_expression=UCRExpression(definition={
                'type': 'dict', 'properties': {'case_type': 'patient'}
            }),
        )
        user = MockUser()
        context = get_evaluation_context(user, 'post', {}, {}, {"resource": {"type": "patient"}})
        self.assertFalse(_apply_api_filter(api_model, context))

    def test_filter_pass(self):
        api_model = _get_api_with_filter(self.domain_name)
        user = MockUser()
        context = get_evaluation_context(user, 'post', {}, {}, {"resource": {"type": "patient"}})
        self.assertTrue(_apply_api_filter(api_model, context))

    def test_filter_fail(self):
        api_model = _get_api_with_filter(self.domain_name)
        user = MockUser()
        context = get_evaluation_context(user, 'post', {}, {}, {"resource": {"type": "client"}})
        with self.assertRaises(GenericInboundRequestFiltered):
            _apply_api_filter(api_model, context)

    def test_validation_pass(self):
        api_model = _get_api_with_validation(self.domain_name)
        user = MockUser()
        context = get_evaluation_context(user, 'post', {}, {}, {"resource": {"type": "patient"}})
        self.assertTrue(_validate_api_request(api_model, context))

    def test_validation_errors(self):
        api_model = _get_api_with_validation(self.domain_name)
        validations = api_model.get_validations()
        client_validation_expression = UCRExpression(
            expression_type=UCR_NAMED_FILTER,
            definition={
                "type": "boolean_expression",
                "expression": {"type": "jsonpath", "jsonpath": "body.resource.type"},
                "operator": "not_eq",
                "property_value": "client"
            })
        validations.append(ConfigurableApiValidation(
            api=api_model,
            name="is also patient",
            message="must be patient again",
            expression=client_validation_expression,
        ))
        user = MockUser()
        # 1st validation should fail, 2nd should succeed
        context = get_evaluation_context(user, 'post', {}, {}, {"resource": {"type": "employee"}})
        with self.assertRaises(GenericInboundValidationError) as cm:
            _execute_generic_api(self.domain_name, user, "device_id", context, api_model)

        self.assertEqual(cm.exception.errors, [
            {"name": "is patient", "message": "must be patient"},
        ])


@flag_enabled("UCR_EXPRESSION_REGISTRY")
class TestGenericInboundAPINamedExpression(TestCase):
    """Test that named expressions can be used with ConfigurableAPI"""
    domain_name = "test_named"

    @classmethod
    def setUpTestData(cls):
        cls.filter = UCRExpression.objects.create(
            domain=cls.domain_name,
            name="patient_case_filter",
            expression_type=UCR_NAMED_FILTER,
            definition={
                "type": "boolean_expression",
                "expression": {"type": "jsonpath", "jsonpath": "body.resource.type"},
                "operator": "not_eq",
                "property_value": "client"
            }
        )

        cls.expression = UCRExpression.objects.create(
            domain=cls.domain_name,
            name="patient_case_create",
            expression_type=UCR_NAMED_EXPRESSION,
            definition={"type": "dict", "properties": {"case_type": "patient"}}
        )

    def test_named_filter(self):
        api_model = ConfigurableAPI(
            domain=self.domain_name,
            filter_expression=UCRExpression(
                expression_type=UCR_NAMED_FILTER,
                definition={"type": "named", "name": "patient_case_filter"}
            ),
        )
        # this also tests that an exception isn't raised
        self.assertIsNotNone(api_model.parsed_filter)

    def test_named_expression(self):
        api_model = ConfigurableAPI(
            domain=self.domain_name,
            transform_expression=UCRExpression(
                expression_type=UCR_NAMED_EXPRESSION,
                definition={"type": "named", "name": "patient_case_create"}
            ),
        )
        # this also tests that an exception isn't raised
        self.assertIsNotNone(api_model.parsed_transform_expression)

    def test_named_expression_in_validation(self):
        validation_expression = UCRExpression.objects.create(
            expression_type=UCR_NAMED_FILTER,
            definition={"type": "named", "name": "patient_case_filter"}
        )

        api_model = ConfigurableAPI.objects.create(domain=self.domain_name, transform_expression=self.expression)
        ConfigurableApiValidation.objects.create(
            api=api_model, name="is patient", message="must be patient", expression=validation_expression
        )
        # this also tests that an exception isn't raised
        self.assertIsNotNone(api_model.get_validations()[0].parsed_expression)


def _get_api_with_validation(domain_name, expression=None):
    api_model = ConfigurableAPI(
        domain=domain_name,
        transform_expression=UCRExpression(definition={
            'type': 'dict', 'properties': {'case_type': 'patient'}
        }),
    )
    validation_expression = UCRExpression(
        expression_type=UCR_NAMED_FILTER,
        definition={
            "type": "boolean_expression",
            "expression": {"type": "jsonpath", "jsonpath": "body.resource.type"},
            "operator": "eq",
            "property_value": "patient"
        })
    validations = [
        ConfigurableApiValidation(
            api=api_model,
            name="is patient",
            message="must be patient",
            expression=validation_expression,
        )
    ]
    # mock 'get_validations'
    api_model.get_validations = lambda: validations
    return api_model


def _get_api_with_filter(domain_name):
    filter_expression = UCRExpression(
        expression_type=UCR_NAMED_FILTER,
        definition={
            "type": "boolean_expression",
            "expression": {"type": "jsonpath", "jsonpath": "body.resource.type"},
            "operator": "eq",
            "property_value": "patient"
        })
    api_model = ConfigurableAPI(
        domain=domain_name,
        filter_expression=filter_expression,
        transform_expression=UCRExpression(definition={
            'type': 'dict', 'properties': {'case_type': 'patient'}
        }),
    )
    return api_model
