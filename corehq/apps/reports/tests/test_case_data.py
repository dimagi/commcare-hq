import uuid

from copy import deepcopy
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.http import HttpRequest
from django.test import TestCase
from unittest.mock import patch

from casexml.apps.case.mock import CaseBlock

from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyGroup,
    CaseType,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.reports.standard.cases.case_data import (
    _get_case_property_tables,
    get_case_and_display_data,
    get_cases_and_forms_for_deletion,
    soft_delete_cases_and_forms,
    MAX_CASE_COUNT,
    MAX_SUBCASE_DEPTH
)
from corehq.apps.reports.views import archive_form
from corehq.apps.users.models import (
    WebUser,
    HqPermissions,
    UserRole
)
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.util.test_utils import unit_testing_only


@patch('corehq.apps.reports.standard.cases.case_data.domain_has_privilege', lambda _, __: True)
class TestCaseData(TestCase):

    def setUp(self) -> None:
        self.domain = "test-dd-domain"
        self.case_type = "case-test"
        self.timezone = "Asia/Kolkata"

    def tearDown(self) -> None:
        CaseProperty.objects.all().delete()
        CasePropertyGroup.objects.all().delete()
        CaseType.objects.all().delete()

    def test_no_data_dictionary(self):
        dynamic_data = {"prop1": None, "prop2": None}
        result = _get_case_property_tables(self.domain, self.case_type, dynamic_data, self.timezone)
        self._assert_grouping_order_tables(result, [{"name": None, "properties": ["prop1", "prop2"]}])

    def test_dd_ordering_when_single_group(self):
        """
        Tests that when a data dictionary contains only one user defined group,
        properties within the group is retained.
        """
        # Create group1 properties
        self._create_case_property("prop1", "group1")
        self._create_case_property("prop2", "group1")
        result = _get_case_property_tables(self.domain, self.case_type, {}, self.timezone)
        self._assert_grouping_order_tables(result, [{"name": "group1", "properties": ["prop1", "prop2"]}])

    def test_dd_ordering_when_multiple_groups(self):
        """
        Tests that when a data dictionary contains multiple user defined groups,
        ordering of groups and properties within the group is retained.
        """
        # Create group1 properties
        self._create_case_property("prop1", "group1")
        self._create_case_property("prop2", "group1")
        self._create_case_property("prop3", "group2")
        self._create_case_property("prop4", "group2")
        result = _get_case_property_tables(self.domain, self.case_type, {}, self.timezone)
        self._assert_grouping_order_tables(result, [{"name": "group1", "properties": ["prop1", "prop2"]},
                                                    {"name": "group2", "properties": ["prop3", "prop4"]}])

    def test_dd_ordering_when_multiple_groups_and_unrecognized_group(self):
        """
        Tests that when a data dictionary contains multiple user defined groups and a unrecognized group,
        ordering of groups and properties within the group is retained. Ordering is not retained in
        unrecognized group.
        """
        # Create group1 properties
        self._create_case_property("prop1", "group1")
        self._create_case_property("prop2", "group1")
        self._create_case_property("prop3", "group2")
        self._create_case_property("prop4", "group2")

        # Dynamic data with additional property not present in any of the groups
        dynamic_data = {"prop1": None, "prop2": None, "prop3": None, "prop4": None, "prop5": None, "prop6": None}

        result = _get_case_property_tables(self.domain, self.case_type, dynamic_data, self.timezone)
        self._assert_grouping_order_tables(result, [{"name": "group1", "properties": ["prop1", "prop2"]},
                                                    {"name": "group2", "properties": ["prop3", "prop4"]},
                                                    {"name": "Unrecognized", "properties": ["prop5", "prop6"]}
                                                    ])

    def _assert_grouping_order_tables(self, result, expected_result):
        """
        Sample result
        [{'name': 'group1', 'rows': [[{'expr': 'prop1', 'name': 'prop1', 'description': '', 'value': '---',
        'has_history': True}, {'expr': 'prop2', 'name': 'prop2', 'description': '', 'value': '---',
        'has_history': True}]]}, {'name': 'group2', 'rows': [[{'expr': 'prop3', 'name': 'prop3',
        'description': '', 'value': '---', 'has_history': True}, {'expr': 'prop4', 'name': 'prop4',
        'description': '', 'value': '---', 'has_history': True}]]}]
        """
        for group_data, expected_group_data in zip(result, expected_result):
            group_name_actual = group_data.get("name")
            group_name_expected = expected_group_data.get("name")
            self.assertEqual(group_name_expected, group_name_actual)
            rows_actual = group_data.get("rows")[0]
            props_actual = [prop.get("name") for prop in rows_actual]
            if not group_name_actual or group_name_actual == "Unrecognized":
                # Ordering of properties in unrecognized group is not user defined
                self.assertEqual(set(expected_group_data.get("properties")), set(props_actual))
            else:
                self.assertEqual(expected_group_data.get("properties"), props_actual)

    def _create_case_property(self, prop_name, group=None):
        case_type_obj = CaseType.get_or_create(self.domain, self.case_type)
        group_obj = None
        if group:
            group_obj, _ = CasePropertyGroup.objects.get_or_create(name=group, case_type=case_type_obj)
        CaseProperty.objects.get_or_create(case_type=case_type_obj, name=prop_name, group=group_obj)


@unit_testing_only
def _delete_all_cases_and_forms(domain):
    call_command('hard_delete_forms_and_cases_in_domain', domain, noinput=True, ignore_domain_in_use=True)


@es_test(requires=[form_adapter])
class TestCaseDeletion(TestCase):
    # For more form archiving related tests see test_rebuild.py

    @classmethod
    def setUpClass(cls):
        super(TestCaseDeletion, cls).setUpClass()
        cls.domain = "test-domain"
        domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(domain_obj.delete)
        cls.request = HttpRequest()
        cls.request.domain = cls.domain
        cls.request.can_access_all_locations = True
        cls.request.method = 'POST'
        role = UserRole.create(
            cls.domain, 'test-role', permissions=HqPermissions(
                edit_data=True, view_reports=True
            )
        )
        couch_user = WebUser.create(cls.domain, 'user', 'password', None, None, role_id=role.get_id)
        cls.addClassCleanup(couch_user.delete, None, None)
        couch_user.is_authenticated = True
        cls.request.user = couch_user

    def make_simple_case(self):
        main_case_id = uuid.uuid4().hex
        submit_case_blocks([
            CaseBlock(main_case_id, create=True).as_text(),
        ], self.domain)
        submit_case_blocks([
            CaseBlock(main_case_id, update={}).as_text(),
        ], self.domain)
        self.addCleanup(_delete_all_cases_and_forms, self.domain)

        return main_case_id

    def make_complex_case(self, xform_delete=False):
        main_case_id = uuid.uuid4().hex
        child_case1_id = uuid.uuid4().hex
        child_case2_id = uuid.uuid4().hex
        sub_child1_id = uuid.uuid4().hex
        sub_child2_id = uuid.uuid4().hex
        submit_case_blocks([
            CaseBlock(main_case_id, case_name="main_case", create=True).as_text(),
            CaseBlock(child_case1_id, case_name="child1", create=True).as_text(),
        ], self.domain)
        xform, cases = submit_case_blocks([
            CaseBlock(main_case_id, update={}).as_text(),
            CaseBlock(child_case2_id, case_name="child2", create=True).as_text(),
        ], self.domain)
        submit_case_blocks([
            CaseBlock(child_case1_id, update={}).as_text(),
            CaseBlock(sub_child1_id, case_name="sub1", create=True).as_text(),
        ], self.domain)
        submit_case_blocks([
            CaseBlock(child_case2_id, update={}).as_text(),
            CaseBlock(sub_child2_id, case_name="sub2", create=True).as_text(),
        ], self.domain)
        self.addCleanup(_delete_all_cases_and_forms, self.domain)

        if xform_delete:
            for case in cases:
                if case.case_id != main_case_id:
                    return xform, case
        return main_case_id

    def make_closed_case(self):
        main_case_id = uuid.uuid4().hex
        other_case_id = uuid.uuid4().hex
        submit_case_blocks([
            CaseBlock(main_case_id, create=True).as_text(),
        ], self.domain)
        submit_case_blocks([
            CaseBlock(other_case_id, create=True).as_text(),
        ], self.domain)
        submit_case_blocks([
            CaseBlock(main_case_id, update={}).as_text(),
            CaseBlock(other_case_id, create=False, close=True).as_text(),
        ], self.domain)
        self.addCleanup(_delete_all_cases_and_forms, self.domain)

        return main_case_id, other_case_id

    def make_affected_case(self):
        main_case_id = uuid.uuid4().hex
        other_case_id = uuid.uuid4().hex
        submit_case_blocks([
            CaseBlock(main_case_id, create=True).as_text(),
        ], self.domain)
        submit_case_blocks([
            CaseBlock(other_case_id, create=True).as_text(),
        ], self.domain)
        submit_case_blocks([
            CaseBlock(main_case_id, update={}).as_text(),
            CaseBlock(other_case_id, update={}).as_text(),
        ], self.domain)
        self.addCleanup(_delete_all_cases_and_forms, self.domain)

        return main_case_id, other_case_id

    # Testing case data retrieval
    def test_case_walk_returns_right_number_of_cases(self):
        case_id = self.make_complex_case()
        case = CommCareCase.objects.get_case(case_id, self.domain)
        case_data = get_case_and_display_data(case, self.domain)

        self.assertEqual(len(case_data['case_delete_list']), 5)

    def test_case_walk_returns_right_number_of_forms(self):
        case_id = self.make_complex_case()
        case = CommCareCase.objects.get_case(case_id, self.domain)
        case_data = get_case_and_display_data(case, self.domain)

        self.assertEqual(len(case_data['form_delete_list']), 4)

    def test_form_list_archives_without_error(self):
        """
        Ensure that for a case with mulitple subcases, each with their own subcases, the archive_form function
        doesn't throw an error, which means that the list of forms returned by get_cases_and_forms_for_deletion are
        correctly ordered such that the create form for each case is the last of that case's forms to be archived.
        """
        case_id = self.make_complex_case()
        case = CommCareCase.objects.get_case(case_id, self.domain)
        case_data = get_case_and_display_data(case, self.domain)

        for form in case_data['form_delete_list']:
            self.assertTrue(archive_form(self.request, self.domain, form, is_case_delete=True))

    def test_case_walk_returns_right_number_of_affected_cases(self):
        main_case_id, _ = self.make_affected_case()
        case = CommCareCase.objects.get_case(main_case_id, self.domain)
        case_data = get_case_and_display_data(case, self.domain)

        self.assertEqual(len(case_data['affected_cases']), 1)

    def test_case_walk_returns_right_number_of_reopened_cases(self):
        main_case_id, _ = self.make_closed_case()
        case = CommCareCase.objects.get_case(main_case_id, self.domain)
        case_data = get_case_and_display_data(case, self.domain)

        self.assertEqual(len(case_data['reopened_cases']), 1)

    # Testing case data retrieval for form driven case deletion
    def test_case_walk_returns_form_delete_case_list(self):
        xform, case = self.make_complex_case(xform_delete=True)
        case_data = get_case_and_display_data(case, self.domain, xform.form_id)

        self.assertEqual(len(case_data['form_delete_cases']), 1)
        self.assertEqual(len(case_data['delete_cases']), 1)

    def test_case_walk_returns_form_delete_affected_list(self):
        xform, case = self.make_complex_case(xform_delete=True)
        case_data = get_case_and_display_data(case, self.domain, xform.form_id)

        self.assertEqual(len(case_data['form_affected_cases']), 1)

    # Testing deletion
    def test_delete_case(self):
        """
        Ensure that a single case with two forms is soft deleted
        """
        case_id = self.make_simple_case()

        delete_dict = get_cases_and_forms_for_deletion(self.request, self.domain, case_id)
        soft_delete_cases_and_forms(self.request, self.domain,
                                    delete_dict['case_delete_list'], delete_dict['form_delete_list'])

        case = CommCareCase.objects.get_case(case_id, self.domain)
        self.assertTrue(case.is_deleted)

    def test_delete_submission_forms(self):
        """
        Ensure that for a case with mulitple subcases, each with their own subcases, all related submission
        forms are archived and soft deleted
        """
        case_id = self.make_complex_case()

        delete_dict = get_cases_and_forms_for_deletion(self.request, self.domain, case_id)
        soft_delete_cases_and_forms(self.request, self.domain,
                                    delete_dict['case_delete_list'], delete_dict['form_delete_list'])

        for form in delete_dict['form_delete_list']:
            form = XFormInstance.objects.get_form(form, self.domain)
            self.assertTrue(form.is_archived)
            self.assertTrue(form.is_deleted)

    def test_delete_multiple_related_cases(self):
        """
        Ensure that a case with mulitple subcases, each with their own subcases are all soft deleted
        """
        case_id = self.make_complex_case()

        delete_dict = get_cases_and_forms_for_deletion(self.request, self.domain, case_id)
        soft_delete_cases_and_forms(self.request, self.domain,
                                    delete_dict['case_delete_list'], delete_dict['form_delete_list'])

        for case in delete_dict['case_delete_list']:
            case_obj = CommCareCase.objects.get_case(case, self.domain)
            self.assertTrue(case_obj.is_deleted)

    def test_delete_case_that_closes_another_case(self):
        """
        Ensure that when a case with a submission form that closed another case is deleted, that other
        case is re-opened. This is really testing form archiving but here for completeness.
        """
        main_case_id, other_case_id = self.make_closed_case()

        other_case = CommCareCase.objects.get_case(other_case_id, self.domain)
        self.assertTrue(other_case.closed)

        delete_dict = get_cases_and_forms_for_deletion(self.request, self.domain, main_case_id)
        soft_delete_cases_and_forms(self.request, self.domain,
                                    delete_dict['case_delete_list'], delete_dict['form_delete_list'])

        other_case = CommCareCase.objects.get_case(other_case_id, self.domain)
        self.assertFalse(other_case.closed)

    def test_delete_case_that_updates_another_case(self):
        """
        Ensure that when a case with a submission form that updates another case is deleted, that form doesn't
        appear in the other case's xform_ids. This is really testing form archiving but here for completeness.
        """
        main_case_id, other_case_id = self.make_affected_case()

        other_case = CommCareCase.objects.get_case(other_case_id, self.domain)
        self.assertEqual(len(other_case.xform_ids), 2)

        delete_dict = get_cases_and_forms_for_deletion(self.request, self.domain, main_case_id)
        soft_delete_cases_and_forms(self.request, self.domain,
                                    delete_dict['case_delete_list'], delete_dict['form_delete_list'])

        other_case = CommCareCase.objects.get_case(other_case_id, self.domain)
        self.assertEqual(len(other_case.xform_ids), 1)

    # Test error handling
    def test_case_deletion_errors_if_too_many_cases(self):
        """
        Ensure that a case with more than 100 related cases throws an error
        """
        request = deepcopy(self.request)
        setattr(request, 'session', 'session')
        setattr(request, '_messages', FallbackStorage(request))

        main_case_id = uuid.uuid4().hex
        for i in range(MAX_CASE_COUNT):
            child_case_id = uuid.uuid4().hex
            submit_case_blocks([
                CaseBlock(main_case_id, create=True).as_text(),
                CaseBlock(child_case_id, create=True).as_text(),
            ], self.domain)
        self.addCleanup(_delete_all_cases_and_forms, self.domain)

        return_dict = get_cases_and_forms_for_deletion(request, self.domain, main_case_id)
        self.assertTrue(return_dict['redirect'])

    def test_case_deletion_errors_if_too_many_subcases(self):
        """
        Ensure that a case with 3 or more nested subcases throws an error
        """
        request = deepcopy(self.request)
        setattr(request, 'session', 'session')
        setattr(request, '_messages', FallbackStorage(request))

        cases = [uuid.uuid4().hex for i in range(MAX_SUBCASE_DEPTH + 1)]
        for i in range(MAX_SUBCASE_DEPTH):
            submit_case_blocks([
                CaseBlock(cases[i], create=True).as_text(),
                CaseBlock(cases[i + 1], create=True).as_text(),
            ], self.domain)
        self.addCleanup(_delete_all_cases_and_forms, self.domain)

        return_dict = get_cases_and_forms_for_deletion(request, self.domain, cases[0])
        self.assertTrue(return_dict['redirect'])
