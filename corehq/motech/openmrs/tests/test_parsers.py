from __future__ import absolute_import
from __future__ import unicode_literals
import json
from unittest import TestCase

from mock import Mock

from corehq.motech.openmrs.repeater_helpers import get_patient_by_identifier


PATIENT_SEARCH_RESPONSE = json.loads("""{
    "results": [
        {
            "auditInfo": "REDACTED",
            "display": "REDACTED",
            "identifiers": [
                {
                    "display": "REDACTED",
                    "identifier": "00000000/00/0000",
                    "identifierType": {
                        "display": "REDACTED",
                        "links": "REDACTED",
                        "uuid": "e2b966d0-1d5f-11e0-b929-000c29ad1d07"
                    },
                    "links": "REDACTED",
                    "location": "REDACTED",
                    "preferred": true,
                    "resourceVersion": "1.8",
                    "uuid": "ee1df764-2c2e-4e58-aa4a-1e07bd41301f",
                    "voided": false
                }
            ],
            "links": "REDACTED",
            "person": "REDACTED",
            "resourceVersion": "1.8",
            "uuid": "672c4a51-abad-4b5e-950c-10bc262c9c1a",
            "voided": false
        },
        {
            "auditInfo": "REDACTED",
            "display": "REDACTED",
            "identifiers": [
                {
                    "display": "REDACTED",
                    "identifier": "11111111/11/1111",
                    "identifierType": {
                        "display": "REDACTED",
                        "links": "REDACTED",
                        "uuid": "e2b966d0-1d5f-11e0-b929-000c29ad1d07"
                    },
                    "links": "REDACTED",
                    "location": "REDACTED",
                    "preferred": true,
                    "resourceVersion": "1.8",
                    "uuid": "648254a4-3a13-4e50-b315-e943bd87b58b",
                    "voided": false
                }
            ],
            "links": "REDACTED",
            "person": "REDACTED",
            "resourceVersion": "1.8",
            "uuid": "5ba94fa2-9cb3-4ae6-b400-7bf45783dcbf",
            "voided": false
        }
    ]
}""")


class GetPatientTest(TestCase):
    def test_get_patient_by_identifier(self):
        response_mock = Mock()
        response_mock.json.return_value = PATIENT_SEARCH_RESPONSE
        requests_mock = Mock()
        requests_mock.get.return_value = response_mock

        patient = get_patient_by_identifier(
            requests_mock, 'e2b966d0-1d5f-11e0-b929-000c29ad1d07', '11111111/11/1111')
        self.assertEqual(patient['uuid'], '5ba94fa2-9cb3-4ae6-b400-7bf45783dcbf')
