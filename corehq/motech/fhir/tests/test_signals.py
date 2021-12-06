from couchforms.signals import successful_form_received
from nose.tools import assert_in


def test_create_fhir_repeat_records_in_receivers():
    receivers = [r[1]().__name__ for r in successful_form_received.receivers]
    assert_in('create_fhir_repeat_records', receivers)
