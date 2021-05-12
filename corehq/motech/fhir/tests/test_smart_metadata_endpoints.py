import json

from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from corehq.motech.fhir.const import FHIR_VERSION_4_0_1
from corehq.motech.fhir.utils import build_capability_statement
from corehq.motech.fhir.views import SmartAuthView, SmartTokenView
from corehq.util.test_utils import flag_enabled
from corehq.util.view_utils import absolute_reverse


class TestConfigurationView(TestCase):

    def test_configuration_view(self):
        with flag_enabled('FHIR_INTEGRATION'):
            response = Client().get(
                reverse("smart_configuration_view", kwargs={
                    'domain': "test",
                    "fhir_version_name": "R4"
                })
            )

        json_content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(
            json_content['authorization_endpoint'],
            absolute_reverse(SmartAuthView.urlname, kwargs={"domain": "test"})
        )
        self.assertEqual(
            json_content['token_endpoint'], absolute_reverse(SmartTokenView.urlname, kwargs={"domain": "test"})
        )


class TestCapabilityStatement(TestCase):

    def test_capability_statement(self):
        statement = build_capability_statement("test_domain", FHIR_VERSION_4_0_1)
        expected_statement = {
            "date":
                "2021-03-23",
            "fhirVersion":
                "4.0.1",
            "kind":
                "instance",
            "status":
                "active",
            "format": ["json"],
            "rest": [{
                "mode": "server",
                "security": {
                    "service": [{
                        "coding": [{
                            "code": "SMART-on-FHIR",
                            "system": "http://hl7.org/fhir/restful-security-service"
                        }]
                    }],
                    "extension": [{
                        "extension": [{
                            "valueUri": absolute_reverse(SmartTokenView.urlname, kwargs={"domain": "test_domain"}),
                            "url": "token"
                        }, {
                            "valueUri": absolute_reverse(SmartAuthView.urlname, kwargs={"domain": "test_domain"}),
                            "url": "authorize"
                        }],
                        "url": "http://fhir-registry.smarthealthit.org/StructureDefinition/oauth-uris"
                    }]
                }
            }]
        }
        self.assertDictEqual(statement, expected_statement)
