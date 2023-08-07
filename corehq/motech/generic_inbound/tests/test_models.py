from django.core.exceptions import FieldError
from django.test import TestCase
from field_audit.models import AuditEvent
from nose.tools import nottest

from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from corehq.apps.userreports.models import UCRExpression
from corehq.apps.userreports.specs import EvaluationContext
from corehq.motech.generic_inbound.models import ConfigurableAPI


class TestGenericInboundModels(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = _make_api_for_test('test', 'test api')

    def test_key_created(self):
        self.assertIsNotNone(self.api.url_key)
        self.assertTrue(len(self.api.url_key) > 0)

    def test_key_read_only(self):
        self.assertIsNotNone(self.api.url_key)
        self.api.url_key = 'new key'
        with self.assertRaisesRegex(FieldError, "'url_key' can not be changed"):
            self.api.save()

    def test_transform(self):
        body = {'name': 'cricket', 'is_team_sport': True}
        result = self.api.parsed_expression(body, EvaluationContext(body))
        self.assertEqual(result, {'case_type': 'sport', 'case_name': 'cricket', 'is_team_sport': True})


class TestConfigurableApiAuditing(TestCase):
    domain = "test-api-auditing"
    qualified_model_name = "corehq.motech.generic_inbound.models.ConfigurableAPI"
    audit_fields = {
        "domain",
        "name",
        "url_key",
        "transform_expression",
    }

    @classmethod
    def setUpTestData(cls):
        AuditEvent.objects.all().delete()

        cls.expression1 = UCRExpression.objects.create(
            name='create_sport',
            domain=cls.domain,
            expression_type=UCR_NAMED_EXPRESSION,
            definition={
                'type': 'dict',
                'properties': {
                    'case_type': 'sport',
                }
            },
        )

        cls.expression2 = UCRExpression.objects.create(
            name='create_sport_beta',
            domain=cls.domain,
            expression_type=UCR_NAMED_EXPRESSION,
            definition={
                'type': 'dict',
                'properties': {
                    'case_type': 'sport',
                }
            },
        )

    def setUp(self):
        self.api_config = _make_api_for_test(self.domain, "Sports", self.expression1)

        self.setup_audit_events = AuditEvent.objects.all()
        self.setup_event_ids = set(self.setup_audit_events.values_list("id", flat=True))

    @nottest
    def get_test_audit_events(self):
        return AuditEvent.objects.exclude(id__in=self.setup_event_ids)

    def test_audit_fields_for_api_create(self):
        setup_event = self.setup_audit_events[0]
        self.assertEqual(self.qualified_model_name, setup_event.object_class_path)
        self.assertEqual(self.api_config.pk, setup_event.object_pk)
        self.assertTrue(setup_event.is_create)
        self.assertEqual(self.audit_fields, set(setup_event.delta))
        self.assertEqual({"new": self.domain}, setup_event.delta["domain"])
        self.assertEqual({"new": self.api_config.name}, setup_event.delta["name"])
        self.assertEqual({"new": self.expression1.pk}, setup_event.delta["transform_expression"])

    def test_audit_fields_for_api_update(self):
        previous_name = self.api_config.name
        previous_expression = self.api_config.transform_expression
        self.api_config.name = "Sport API Test"
        self.api_config.transform_expression = self.expression2
        self.api_config.save()

        event, = self.get_test_audit_events()
        self.assertEqual(self.qualified_model_name, event.object_class_path)
        self.assertEqual(self.api_config.pk, event.object_pk)
        self.assertFalse(event.is_create)
        self.assertFalse(event.is_delete)
        self.assertEqual(
            {
                "name": {"old": previous_name, "new": "Sport API Test"},
                "transform_expression": {"old": previous_expression.pk, "new": self.expression2.pk}
            },
            event.delta,
        )

    def test_audit_fields_for_api_delete(self):
        api_pk = self.api_config.pk
        self.api_config.delete()
        event, = self.get_test_audit_events()
        self.assertEqual(self.qualified_model_name, event.object_class_path)
        self.assertEqual(api_pk, event.object_pk)
        self.assertTrue(event.is_delete)
        self.assertEqual(self.audit_fields, set(event.delta))
        self.assertEqual({"old": self.api_config.domain}, event.delta["domain"])
        self.assertEqual({"old": self.api_config.url_key}, event.delta["url_key"])
        self.assertEqual({"old": self.api_config.name}, event.delta["name"])
        self.assertEqual({"old": self.expression1.pk}, event.delta["transform_expression"])


def _make_api_for_test(domain, name, expression=None):
    if not expression:
        expression = UCRExpression.objects.create(
            name='create_sport',
            domain=domain,
            expression_type=UCR_NAMED_EXPRESSION,
            definition={
                'type': 'dict',
                'properties': {
                    'case_type': 'sport',
                    'case_name': {
                        'type': 'jsonpath',
                        'jsonpath': 'name',
                    },
                    'is_team_sport': {
                        'type': 'jsonpath',
                        'jsonpath': 'is_team_sport'
                    }
                }
            },
        )

    return ConfigurableAPI.objects.create(
        domain=domain,
        name=name,
        transform_expression=expression
    )
