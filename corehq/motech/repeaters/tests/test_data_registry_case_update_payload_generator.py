import uuid
from unittest.mock import patch, Mock
from xml.etree import cElementTree as ElementTree

from testil import eq, assert_raises

from casexml.apps.case.mock import CaseBlock, IndexAttrs
from casexml.apps.case.xml import V2_NAMESPACE
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.users.models import CouchUser
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCaseSQL, CaseTransaction
from corehq.motech.repeaters.exceptions import DataRegistryCaseUpdateError
from corehq.motech.repeaters.models import DataRegistryCaseUpdateRepeater, Repeater
from corehq.motech.repeaters.repeater_generators import DataRegistryCaseUpdatePayloadGenerator, SYSTEM_FORM_XMLNS

TARGET_DOMAIN = "target_domain"

SOURCE_DOMAIN = "source_domain"


def test_generator_empty_update():
    _test_payload_generator(intent_case=IntentCaseBuilder().include_props([]).get_case(), expected_updates={})


def test_generator_fail_if_case_domain_mismatch():
    builder = IntentCaseBuilder().include_props([]).target_case(domain="other")

    with assert_raises(DataRegistryCaseUpdateError, msg="Target case not found: 1"):
        _test_payload_generator(intent_case=builder.get_case())


def test_generator_include_list():
    builder = IntentCaseBuilder().case_properties(new_prop="new_prop_val").include_props(["new_prop"])
    _test_payload_generator(intent_case=builder.get_case(), expected_updates={
        "1": {"new_prop": "new_prop_val"}})


def test_generator_exclude_list():
    builder = (
        IntentCaseBuilder()
        .case_properties(new_prop="new_prop_val", target_something="1", other_prop="other_prop_val")
        .exclude_props(["other_prop"])
    )
    _test_payload_generator(intent_case=builder.get_case(), expected_updates={
        "1": {
            "new_prop": "new_prop_val",
            "target_something": "1"
        }})


def test_generator_dont_override_existing():
    builder = (
        IntentCaseBuilder(override_properties=False)
        .case_properties(new_prop="new_prop_val", existing_prop="try override", existing_blank_prop="not blank")
        .exclude_props([])
    )
    _test_payload_generator(intent_case=builder.get_case(), expected_updates={
        "1": {
            "new_prop": "new_prop_val",
        }})


def test_generator_update_create_index_to_parent():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "child").exclude_props([])

    def _get_case(case_id):
        assert case_id == "case2"
        return Mock(domain=TARGET_DOMAIN, case_type="parent_type")

    with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
        _test_payload_generator(intent_case=builder.get_case(), expected_indices={
            "1": {"parent": IndexAttrs("parent_type", "case2", "child")}})


def test_generator_update_create_index_to_host():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "extension").exclude_props([])

    def _get_case(case_id):
        assert case_id == "case2"
        return Mock(domain=TARGET_DOMAIN, case_type="parent_type")

    with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
        _test_payload_generator(intent_case=builder.get_case(), expected_indices={
            "1": {"host": IndexAttrs("parent_type", "case2", "extension")}})


def test_generator_update_create_index_not_found():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "child").exclude_props([])

    with assert_raises(DataRegistryCaseUpdateError, msg="Index case not found: case2"):
        with patch.object(CaseAccessorSQL, 'get_case', side_effect=CaseNotFound):
            _test_payload_generator(intent_case=builder.get_case())


def test_generator_update_create_index_domain_mismatch():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "child").exclude_props([])

    def _get_case(case_id):
        assert case_id == "case2"
        return Mock(domain="not target", case_type="parent_type")

    with assert_raises(DataRegistryCaseUpdateError, msg="Index case not found: case2"):
        with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
            _test_payload_generator(intent_case=builder.get_case())


def test_generator_update_create_index_case_type_mismatch():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "child").exclude_props([])

    def _get_case(case_id):
        assert case_id == "case2"
        return Mock(domain=TARGET_DOMAIN, case_type="not parent")

    with assert_raises(DataRegistryCaseUpdateError, msg="Index case type does not match"):
        with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
            _test_payload_generator(intent_case=builder.get_case())


def test_generator_update_multiple_cases():
    main_case_builder = IntentCaseBuilder().case_properties(new_prop="new_prop_val").exclude_props([])
    subcase1 = (
        IntentCaseBuilder()
        .target_case(case_id="sub1")
        .case_properties(sub1_prop="sub1_val")
        .exclude_props([])
        .get_case()
    )
    subcase2 = (
        IntentCaseBuilder()
        .target_case(case_id="sub2")
        .case_properties(sub2_prop="sub2_val")
        .exclude_props([])
        .get_case()
    )
    main_case_builder.set_subcases([subcase1, subcase2])

    def _get_case(case_id):
        return Mock(domain=TARGET_DOMAIN, case_type="parent", case_id=case_id)

    with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
        _test_payload_generator(intent_case=main_case_builder.get_case(), expected_updates={
            "1": {"new_prop": "new_prop_val"},
            "sub1": {"sub1_prop": "sub1_val"},
            "sub2": {"sub2_prop": "sub2_val"},
        })


def test_generator_required_fields():
    intent_case = CommCareCaseSQL(
        domain=SOURCE_DOMAIN,
        type="registry_case_update",
        case_json={},
        case_id=uuid.uuid4().hex,
        user_id="local_user1"
    )
    expect_missing = ["target_data_registry", "target_domain", "target_case_id", "target_case_type"]
    expected_message = f"Missing required case properties: {', '.join(expect_missing)}"
    with assert_raises(DataRegistryCaseUpdateError, msg=expected_message):
        _test_payload_generator(intent_case=intent_case)


def _test_payload_generator(intent_case, expected_updates=None, expected_indices=None):
    # intent case is the case created in the source domain which is used to trigger the repeater
    # and which contains the config for updating the case in the target domain

    repeater = DataRegistryCaseUpdateRepeater(domain=SOURCE_DOMAIN)
    generator = DataRegistryCaseUpdatePayloadGenerator(repeater)
    generator.submission_user_id = Mock(return_value='user1')
    generator.submission_username = Mock(return_value='user1')

    # target_case is the case in the target domain which is being updated
    def _get_case(self, case_id, case_type, *args, **kwargs):
        return Mock(domain=TARGET_DOMAIN, case_type=case_type, case_id=case_id, case_json={
            "existing_prop": uuid.uuid4().hex,
            "existing_blank_prop": ""
        })

    with patch.object(DataRegistryHelper, "get_case", new=_get_case), \
         patch.object(CouchUser, "get_by_user_id", return_value=Mock(username="local_user")):
        repeat_record = Mock(repeater=Repeater())
        form = DataRegistryUpdateForm(generator.get_payload(repeat_record, intent_case))
        form.assert_form_props({
            "source_domain": SOURCE_DOMAIN,
            "source_form_id": "form123",
            "source_username": "local_user",
        })
        form.assert_case_updates(expected_updates or {})
        if expected_indices:
            form.assert_case_index(expected_indices)


class DataRegistryUpdateForm:
    def __init__(self, form):
        self.formxml = ElementTree.fromstring(form)
        self.cases = {
            case.get('case_id'): CaseBlock.from_xml(case)
            for case in self.formxml.findall("{%s}case" % V2_NAMESPACE)
        }

    def _get_form_value(self, name):
        return self.formxml.find(f"{{{SYSTEM_FORM_XMLNS}}}{name}").text

    def assert_case_updates(self, expected_updates):
        """
        :param expected_updates: Dict[case_id, Dict]
        """
        for case_id, updates in expected_updates.items():
            eq(self.cases[case_id].update, updates)

    def assert_case_index(self, expected_indices):
        """
        :param expected_indices: Dict[case_id, Dict[index_key, IndexAttrs]]
        """
        for case_id, indices in expected_indices.items():
            for key, expected in indices.items():
                actual = self.cases[case_id].index[key]
                eq(actual, expected)

    def assert_form_props(self, expected):
        actual = {
            key: self._get_form_value(key)
            for key in expected
        }
        eq(actual, expected)


class IntentCaseBuilder:
    CASE_TYPE = "registry_case_update"

    def __init__(self, registry="registry1", override_properties=True):
        self.props: dict = {
            "target_data_registry": registry,
            "target_property_override": str(int(override_properties)),
        }
        self.target_case()
        self.subcases = []

    def target_case(self, domain=TARGET_DOMAIN, case_id="1", case_type="patient"):
        self.props.update({
            "target_case_id": case_id,
            "target_domain": domain,
            "target_case_type": case_type,
        })
        return self

    def create_index(self, case_id, case_type, relationship="child"):
        self.props.update({
            "target_index_create_case_id": case_id,
            "target_index_create_case_type": case_type,
            "target_index_create_relationship": relationship,
        })
        return self

    def include_props(self, include):
        self.props["target_property_includelist"] = " ".join(include)
        return self

    def exclude_props(self, exclude):
        self.props["target_property_excludelist"] = " ".join(exclude)
        return self

    def case_properties(self, **kwargs):
        self.props.update(kwargs)
        return self

    def set_subcases(self, subcases):
        self.subcases = subcases

    def get_case(self):
        intent_case = CommCareCaseSQL(
            domain=SOURCE_DOMAIN,
            type=self.CASE_TYPE,
            case_json=self.props,
            case_id=uuid.uuid4().hex,
            user_id="local_user1"
        )
        intent_case.track_create(CaseTransaction(form_id="form123", type=CaseTransaction.TYPE_FORM))

        def _mock_subcases(*args, **kwargs):
            return self.subcases

        intent_case.get_subcases = _mock_subcases
        return intent_case
