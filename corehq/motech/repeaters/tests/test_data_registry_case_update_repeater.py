import uuid
from unittest.mock import patch, Mock
from xml.etree import cElementTree as ElementTree

from testil import eq

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2_NAMESPACE
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.form_processor.models import CommCareCaseSQL
from corehq.motech.repeaters.models import DataRegistryCaseUpdateRepeater
from corehq.motech.repeaters.repeater_generators import DataRegistryCaseUpdatePayloadGenerator


def test_data_registry_case_update_payload_generator():
    _test_data_registry_case_update_payload_generator({}, {})


def _test_data_registry_case_update_payload_generator(initial_case_properties, expected_target_props):
    domain = "source_domain"
    repeater = DataRegistryCaseUpdateRepeater(domain=domain)
    generator = DataRegistryCaseUpdatePayloadGenerator(repeater)
    generator.submission_user_id = Mock(return_value='user1')
    generator.submission_username = Mock(return_value='user1')
    intent_case = CommCareCaseSQL(
        type="registry_case_update",
        case_json={
            "target_data_registry": "registry1",
            "target_case_id": "case1",
            "target_case_domain": "target_domain",
            "target_case_type": "patient",
            "target_create_case": "false",
            "target_case_owner_id": "user1",
            "target_index_case_id": "case2",
            "target_index_type": "contact",
            "target_property_ignorelist": "",
            "target_property_includelist": "copy_this",
            "target_property_override": "true",
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
    with patch.object(DataRegistryHelper, "get_case", return_value=[target_case]):
        form = generator.get_payload(None, intent_case)
        formxml = ElementTree.fromstring(form)
        case = CaseBlock.from_xml(formxml.find("{%s}case" % V2_NAMESPACE))
        expected_update = {
            "copy_this": copy_value
        }
        expected_update.update(expected_target_props)
        eq(case.update, expected_update)
