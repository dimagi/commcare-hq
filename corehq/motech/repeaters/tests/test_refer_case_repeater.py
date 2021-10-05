import uuid
from unittest.mock import patch, Mock
from xml.etree import cElementTree as ElementTree

from testil import eq

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2_NAMESPACE
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from corehq.motech.repeaters.models import ReferCaseRepeater
from corehq.motech.repeaters.repeater_generators import ReferCasePayloadGenerator


def test_refer_case_payload_generator_no_previous_transfer():
    _test_refer_case_payload_generator({}, _get_referral_props("1", "source_domain"))


def test_refer_case_payload_generator_previous_transfer_prior_to_history():
    initial_props = {
        "cchq_referral_source_domain": "a",
        "cchq_referral_source_case_id": "2",
    }
    expected_history_props = _get_referral_props("_unknown_ 2 1", "_unknown_ a source_domain")
    _test_refer_case_payload_generator(initial_props, expected_history_props)


def test_refer_case_payload_generator_one_previous_transfer():
    _test_refer_case_payload_generator(
        _get_referral_props("a", "domainA"),
        _get_referral_props("a 1", "domainA source_domain"),
    )


def test_refer_case_payload_generator_multiple_previous_transfer():
    _test_refer_case_payload_generator(
        _get_referral_props("a b", "domainA domainB"),
        _get_referral_props("a b 1", "domainA domainB source_domain"),
    )


def _test_refer_case_payload_generator(initial_case_properties, expected_referral_props):
    domain = "source_domain"
    repeater = ReferCaseRepeater(domain=domain)
    generator = ReferCasePayloadGenerator(repeater)
    generator.submission_user_id = Mock(return_value='user1')
    generator.submission_username = Mock(return_value='user1')
    transfer_case = CommCareCaseSQL(
        type="transfer",
        case_json={
            "cases_to_forward": "case1",
            "new_owner": "owner1",
            "case_types": "patient",
            "patient_whitelist": "copy_this"
        }
    )
    copy_value = uuid.uuid4().hex
    properties = {"copy_this": copy_value}
    properties.update(initial_case_properties or {})
    target_case = CommCareCaseSQL(
        case_id="1",
        type="patient",
        case_json=properties
    )
    with patch.object(CaseAccessors, "get_cases", return_value=[target_case]):
        form = generator.get_payload(None, transfer_case)
        formxml = ElementTree.fromstring(form)
        case = CaseBlock.from_xml(formxml.find("{%s}case" % V2_NAMESPACE))
        expected_update = {
            "cchq_referral_source_domain": domain,
            "cchq_referral_source_case_id": "1",
            "copy_this": copy_value
        }
        expected_update.update(expected_referral_props)
        eq(case.update, expected_update)


def _get_referral_props(case_id_history, domain_history):
    return {
        "cchq_referral_case_id_history": case_id_history,
        "cchq_referral_domain_history": domain_history,
    }
