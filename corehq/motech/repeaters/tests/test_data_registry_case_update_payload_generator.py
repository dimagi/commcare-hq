import uuid
from datetime import datetime
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

    with assert_raises(DataRegistryCaseUpdateError, msg="Case not found: 1"):
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


def test_generator_create_case():
    builder = IntentCaseBuilder().case_properties(new_prop="new_prop_val").create_case("123")
    _test_payload_generator(
        intent_case=builder.get_case(), registry_mock_cases={},
        expected_updates={"1": {"new_prop": "new_prop_val"}},
        expected_creates={"1": {"case_type": "patient", "owner_id": "123"}},
    )


def test_generator_create_case_target_exists():
    builder = IntentCaseBuilder().case_properties(new_prop="new_prop_val").create_case("123")

    with assert_raises(DataRegistryCaseUpdateError, msg="Unable to create case as it already exists: 1"):
        _test_payload_generator(intent_case=builder.get_case())


def test_generator_create_close():
    builder = IntentCaseBuilder().case_properties(new_prop="new_prop_val").close_case()
    _test_payload_generator(
        intent_case=builder.get_case(),
        expected_updates={"1": {"new_prop": "new_prop_val"}},
        expected_close=["1"],
    )


def test_generator_update_create_index_to_parent():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "child")

    def _get_case(case_id):
        assert case_id == "case2"
        return Mock(domain=TARGET_DOMAIN, type="parent_type")

    with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
        _test_payload_generator(intent_case=builder.get_case(), expected_indices={
            "1": {"parent": IndexAttrs("parent_type", "case2", "child")}})


def test_generator_update_create_index_to_host():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "extension")

    def _get_case(case_id):
        assert case_id == "case2"
        return Mock(domain=TARGET_DOMAIN, type="parent_type")

    with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
        _test_payload_generator(intent_case=builder.get_case(), expected_indices={
            "1": {"host": IndexAttrs("parent_type", "case2", "extension")}})


def test_generator_update_create_index_not_found():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "child")

    with assert_raises(DataRegistryCaseUpdateError, msg="Index case not found: case2"):
        with patch.object(CaseAccessorSQL, 'get_case', side_effect=CaseNotFound):
            _test_payload_generator(intent_case=builder.get_case())


def test_generator_update_create_index_domain_mismatch():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "child")

    def _get_case(case_id):
        assert case_id == "case2"
        return Mock(domain="not target", type="parent_type")

    with assert_raises(DataRegistryCaseUpdateError, msg="Index case not found: case2"):
        with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
            _test_payload_generator(intent_case=builder.get_case())


def test_generator_update_create_index_case_type_mismatch():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "child")

    def _get_case(case_id):
        assert case_id == "case2"
        return Mock(domain=TARGET_DOMAIN, type="not parent")

    with assert_raises(DataRegistryCaseUpdateError, msg="Index case type does not match"):
        with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
            _test_payload_generator(intent_case=builder.get_case())


def test_generator_update_create_index_bad_relationship():
    builder = IntentCaseBuilder().create_index("case2", "parent_type", "cousin")
    msg = "Index relationships must be either 'child' or 'extension'"
    with assert_raises(DataRegistryCaseUpdateError, msg=msg):
        _test_payload_generator(intent_case=builder.get_case())


def test_generator_update_remove_index_bad_relationship():
    builder = IntentCaseBuilder().remove_index("case2", "cousin")
    msg = "Index relationships must be either 'child' or 'extension'"
    with assert_raises(DataRegistryCaseUpdateError, msg=msg):
        _test_payload_generator(intent_case=builder.get_case())


def test_generator_update_remove_index():
    builder = IntentCaseBuilder().remove_index("parent_case_id", "child")

    _test_payload_generator(intent_case=builder.get_case(), expected_indices={
        "1": {"parent": IndexAttrs("parent_type", None, "child")}})


def test_generator_update_create_and_remove_index():
    builder = IntentCaseBuilder() \
        .create_index("case2", "host_type", "extension") \
        .remove_index("parent_case_id", "child")

    def _get_case(case_id):
        assert case_id == "case2"
        return Mock(domain=TARGET_DOMAIN, type="host_type")

    with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
        _test_payload_generator(intent_case=builder.get_case(), expected_indices={
            "1": {
                "host": IndexAttrs("host_type", "case2", "extension"),
                "parent": IndexAttrs("parent_type", None, "child")
            }})


def test_generator_update_create_and_remove_same_index():
    builder = IntentCaseBuilder() \
        .create_index("case2", "new_parent_type", "child") \
        .remove_index("parent_case_id", "child")

    def _get_case(case_id):
        assert case_id == "case2"
        return Mock(domain=TARGET_DOMAIN, type="new_parent_type")

    with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
        _test_payload_generator(intent_case=builder.get_case(), expected_indices={
            "1": {
                "parent": IndexAttrs("new_parent_type", "case2", "child")
            }})


def test_generator_update_multiple_cases():
    main_case_builder = IntentCaseBuilder().case_properties(new_prop="new_prop_val")
    subcase1 = (
        IntentCaseBuilder()
        .target_case(case_id="sub1")
        .case_properties(sub1_prop="sub1_val")
        .get_case()
    )
    subcase2 = (
        IntentCaseBuilder()
        .target_case(case_id="sub2")
        .case_properties(sub2_prop="sub2_val")
        .get_case()
    )
    main_case_builder.set_subcases([subcase1, subcase2])

    def _get_case(case_id):
        return Mock(domain=TARGET_DOMAIN, type="parent", case_id=case_id)

    registry_cases = _mock_registry()
    registry_cases["sub1"] = _mock_case("sub1")
    registry_cases["sub2"] = _mock_case("sub2")

    with patch.object(CaseAccessorSQL, 'get_case', new=_get_case):
        _test_payload_generator(
            intent_case=main_case_builder.get_case(),
            registry_mock_cases=registry_cases,
            expected_updates={
                "1": {"new_prop": "new_prop_val"},
                "sub1": {"sub1_prop": "sub1_val"},
                "sub2": {"sub2_prop": "sub2_val"},
            })


def test_generator_update_multiple_cases_multiple_domains():
    main_case_builder = IntentCaseBuilder().case_properties(new_prop="new_prop_val")
    subcase = (
        IntentCaseBuilder()
        .target_case(domain="other_domain", case_id="sub1")
        .case_properties(sub1_prop="sub1_val")
        .get_case()
    )
    main_case_builder.set_subcases([subcase])

    with assert_raises(DataRegistryCaseUpdateError, msg="Multiple updates must all be in the same domain"):
        _test_payload_generator(intent_case=main_case_builder.get_case())


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


def test_generator_copy_from_other_case():
    builder = IntentCaseBuilder() \
        .case_properties(intent_prop="intent_prop_val")\
        .copy_props_from("other_domain", "other_case_id", "other_case_type")

    registry_cases = _mock_registry()
    registry_cases["other_case_id"] = Mock(
        domain="other_domain", case_id="other_case_id", type="other_case_type",
        case_json={"other_prop": "other_val"}
    )

    _test_payload_generator(
        intent_case=builder.get_case(),
        registry_mock_cases=registry_cases,
        expected_updates={
            "1": {
                "intent_prop": "intent_prop_val",
                "other_prop": "other_val",
            }})


def _test_payload_generator(intent_case, registry_mock_cases=None,
                            expected_updates=None, expected_indices=None,
                            expected_creates=None, expected_close=None):
    # intent case is the case created in the source domain which is used to trigger the repeater
    # and which contains the config for updating the case in the target domain

    registry_mock_cases = _mock_registry() if registry_mock_cases is None else registry_mock_cases

    repeater = DataRegistryCaseUpdateRepeater(domain=SOURCE_DOMAIN)
    generator = DataRegistryCaseUpdatePayloadGenerator(repeater)
    generator.submission_user_id = Mock(return_value='user1')
    generator.submission_username = Mock(return_value='user1')

    # target_case is the case in the target domain which is being updated
    def _get_case(self, case_id, *args, **kwargs):
        try:
            return registry_mock_cases[case_id]
        except KeyError:
            raise CaseNotFound

    with patch.object(DataRegistryHelper, "get_case", new=_get_case), \
         patch.object(CouchUser, "get_by_user_id", return_value=Mock(username="local_user")):
        repeat_record = Mock(repeater=Repeater())
        form = DataRegistryUpdateForm(generator.get_payload(repeat_record, intent_case), intent_case)
        form.assert_form_props({
            "source_domain": SOURCE_DOMAIN,
            "source_form_id": "form123",
            "source_username": "local_user",
        })
        form.assert_case_updates(expected_updates or {})
        if expected_indices:
            form.assert_case_index(expected_indices)
        if expected_creates:
            form.assert_case_create(expected_creates)
        if expected_close:
            form.assert_case_close(expected_close)


class DataRegistryUpdateForm:
    def __init__(self, form, intent_case):
        self.intent_case = intent_case
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
            case = self.cases[case_id]
            case.date_modified = self.intent_case.modified_on
            eq(case.update, updates)

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

    def assert_case_create(self, expected_creates):
        for case_id, create in expected_creates.items():
            case = self.cases[case_id]
            eq(case.create, True)
            eq(case.date_opened, self.intent_case.opened_on)
            for key, val in create.items():
                eq(getattr(case, key), val)

    def assert_case_close(self, case_ids):
        for case_id in case_ids:
            eq(self.cases[case_id].close, True)


class IntentCaseBuilder:
    CASE_TYPE = "registry_case_update"

    def __init__(self, registry="registry1"):
        self.props: dict = {
            "target_data_registry": registry,
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

    def create_case(self, owner_id):
        self.props.update({
            "target_case_create": "1",
            "target_case_owner_id": owner_id
        })
        return self

    def close_case(self):
        self.props.update({
            "target_case_close": "1",
        })
        return self

    def create_index(self, case_id, case_type, relationship="child"):
        self.props.update({
            "target_index_create_case_id": case_id,
            "target_index_create_case_type": case_type,
            "target_index_create_relationship": relationship,
        })
        return self

    def remove_index(self, case_id, relationship):
        self.props.update({
            "target_index_remove_case_id": case_id,
            "target_index_remove_relationship": relationship,
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

    def copy_props_from(self, domain, case_id, case_type, includes=None, excludes=None):
        self.props["target_copy_properties_from_case_domain"] = domain
        self.props["target_copy_properties_from_case_id"] = case_id
        self.props["target_copy_properties_from_case_type"] = case_type
        if includes is not None:
            self.props["target_copy_properties_includelist"] = includes
        if excludes is not None:
            self.props["target_copy_properties_excludelist"] = excludes
        return self

    def set_subcases(self, subcases):
        self.subcases = subcases

    def get_case(self):
        utcnow = datetime.utcnow()
        intent_case = CommCareCaseSQL(
            domain=SOURCE_DOMAIN,
            type=self.CASE_TYPE,
            case_json=self.props,
            case_id=uuid.uuid4().hex,
            user_id="local_user1",
            opened_on=utcnow,
            modified_on=utcnow,
        )
        intent_case.track_create(CaseTransaction(form_id="form123", type=CaseTransaction.TYPE_FORM))

        def _mock_subcases(*args, **kwargs):
            return self.subcases

        intent_case.get_subcases = _mock_subcases
        return intent_case


def _mock_registry():
    return {
        "1": _mock_case("1")
    }


def _mock_case(case_id):
    return Mock(domain=TARGET_DOMAIN, type="patient", case_id=case_id, case_json={
        "existing_prop": uuid.uuid4().hex,
        "existing_blank_prop": ""
    }, live_indices=[
        Mock(
            identifier="parent", referenced_type="parent_type",
            referenced_id="parent_case_id", relationship_id="child"
        )
    ])
