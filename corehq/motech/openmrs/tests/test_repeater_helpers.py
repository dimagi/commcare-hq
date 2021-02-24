from unittest import skip

from nose.tools import assert_regexp_matches

from corehq.motech.auth import BasicAuthManager
from corehq.motech.openmrs.repeater_helpers import generate_identifier
from corehq.motech.requests import Requests

DOMAIN = 'openmrs-test'
BASE_URL = 'https://demo.mybahmni.org/openmrs/'
USERNAME = 'superman'
PASSWORD = 'Admin123'

# Patient identifier type for use by the Bahmni Registration System
# https://demo.mybahmni.org/openmrs/admin/patients/patientIdentifierType.form?patientIdentifierTypeId=3
IDENTIFIER_TYPE = '81433852-3f10-11e4-adec-0800271c1b75'


@skip('Uses third-party web services')
def test_generate_identifier():
    auth_manager = BasicAuthManager(USERNAME, PASSWORD)
    requests = Requests(
        DOMAIN,
        BASE_URL,
        verify=False,  # demo.mybahmni.org uses a self-issued cert
        auth_manager=auth_manager,
        logger=dummy_logger,
    )
    identifier = generate_identifier(requests, IDENTIFIER_TYPE)
    assert_regexp_matches(identifier, r'^BAH\d{6}$')  # e.g. BAH203001


def dummy_logger(*args, **kwargs):
    pass
