from couchforms.signals import successful_form_received


def test_create_fhir_repeat_records_in_receivers():
    receivers = [r[1]().__name__ for r in successful_form_received.receivers]
    assert 'create_fhir_repeat_records' in receivers
