import uuid

from datetime import datetime
from copy import deepcopy
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.http import HttpRequest
from django.test import TestCase
from unittest.mock import patch

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xform import TempCaseBlockCache

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
    DeleteCaseView,
    soft_delete_cases_and_forms,
)
from corehq.apps.reports.views import archive_form
from corehq.apps.users.models import (
    WebUser,
    HqPermissions,
    UserRole
)
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.models.forms import TempFormCache
from corehq.form_processor.models.cases import TempCaseCache
from corehq.form_processor.tests.utils import create_case
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

    def _create_view(self, case_id, form_id=None):
        view = DeleteCaseView()
        view.kwargs = {'domain': self.domain, 'case_id': case_id}
        if form_id:
            view.kwargs['xform_id'] = form_id
        view.request = self.request
        view.form_cache = TempFormCache()
        view.case_cache = TempCaseCache()
        view.case_block_cache = TempCaseBlockCache()
        return view

    def make_simple_case(self, scenario):
        cases = {
            'main_case_id': uuid.uuid4().hex,
            'other_case_id': uuid.uuid4().hex,
        }
        xforms = {}
        xform, _ = submit_case_blocks([
            CaseBlock(cases['main_case_id'], create=True).as_text(),
        ], self.domain)
        xforms[xform] = xform.form_id
        if scenario == 'simple':
            return cases, xforms
        xform, _ = submit_case_blocks([
            CaseBlock(cases['other_case_id'], case_name="other_case", create=True).as_text(),
        ], self.domain)
        xforms[xform] = xform.form_id
        if scenario == 'affected':
            xform, _ = submit_case_blocks([
                CaseBlock(cases['main_case_id'], update={}).as_text(),
                CaseBlock(cases['other_case_id'], update={}).as_text(),
            ], self.domain)
        elif scenario == 'closed':
            xform, _ = submit_case_blocks([
                CaseBlock(cases['main_case_id'], update={}).as_text(),
                CaseBlock(cases['other_case_id'], close=True).as_text(),
            ], self.domain)
        xforms[xform] = xform.form_id
        self.addCleanup(_delete_all_cases_and_forms, self.domain)

        return cases, xforms

    def make_complex_case(self, xform_delete=False):
        cases = {
            'main_case_id': uuid.uuid4().hex,
            'child_case1_id': uuid.uuid4().hex,
            'child_case2_id': uuid.uuid4().hex,
            'sub_child1_id': uuid.uuid4().hex,
            'sub_child2_id': uuid.uuid4().hex,
        }
        xforms = {}
        xform, _ = submit_case_blocks([
            CaseBlock(cases['main_case_id'], case_name="main_case", create=True).as_text(),
            CaseBlock(cases['child_case1_id'], case_name="child1", create=True).as_text(),
        ], self.domain)
        xforms[xform] = xform.form_id
        main_xform, main_xform_cases = submit_case_blocks([
            CaseBlock(cases['main_case_id'], update={}).as_text(),
            CaseBlock(cases['child_case2_id'], case_name="child2", create=True).as_text(),
        ], self.domain)
        xforms[main_xform] = main_xform.form_id
        xform, _ = submit_case_blocks([
            CaseBlock(cases['child_case1_id'], update={}).as_text(),
            CaseBlock(cases['sub_child1_id'], case_name="sub1", create=True).as_text(),
        ], self.domain)
        xforms[xform] = xform.form_id
        xform, _ = submit_case_blocks([
            CaseBlock(cases['child_case2_id'], update={}).as_text(),
            CaseBlock(cases['sub_child2_id'], case_name="sub2", create=True).as_text(),
        ], self.domain)
        xforms[xform] = xform.form_id
        self.addCleanup(_delete_all_cases_and_forms, self.domain)

        if xform_delete:
            for form in reversed(list(xforms.keys())):
                form.archive()
            for case in main_xform_cases:
                if case.case_id == cases['child_case2_id']:
                    return main_xform, case
        return cases, xforms

    # Testing case data retrieval
    def test_case_walk_returns_correct_cases(self):
        cases, _ = self.make_complex_case()
        case = CommCareCase.objects.get_case(cases['main_case_id'], self.domain)
        view = self._create_view(case.case_id)
        case_data = view.walk_through_case_forms(case, subcase_count=0)

        self.assertItemsEqual(case_data['case_delete_list'], list(cases.values()))

    def test_case_walk_returns_correct_forms(self):
        cases, xforms = self.make_complex_case()
        case = CommCareCase.objects.get_case(cases['main_case_id'], self.domain)
        view = self._create_view(case.case_id)
        case_data = view.walk_through_case_forms(case, subcase_count=0)

        self.assertItemsEqual(case_data['form_delete_list'], list(xforms.values()))

    def test_form_list_archives_without_error(self):
        """
        Ensure that for a case with mulitple subcases, each with their own subcases, the archive_form function
        succeeds, which means that the list of forms returned by walk_through_case_forms are
        correctly ordered such that the create form for each case is the last of that case's forms to be archived.
        """
        cases, xforms = self.make_complex_case()
        case = CommCareCase.objects.get_case(cases['main_case_id'], self.domain)
        view = self._create_view(case.case_id)
        case_data = view.walk_through_case_forms(case, subcase_count=0)

        for form in case_data['form_delete_list']:
            # returns True if archived successfully
            self.assertTrue(archive_form(self.request, self.domain, form, is_case_delete=True))

    def test_case_walk_returns_correct_affected_cases(self):
        cases, _ = self.make_simple_case(scenario='affected')
        case = CommCareCase.objects.get_case(cases['main_case_id'], self.domain)
        view = self._create_view(case.case_id)
        case_data = view.walk_through_case_forms(case, subcase_count=0)

        self.assertEqual(case_data['affected_cases'][0].name, 'other_case')

    def test_case_walk_returns_correct_reopened_cases(self):
        cases, _ = self.make_simple_case(scenario='closed')
        case = CommCareCase.objects.get_case(cases['main_case_id'], self.domain)
        view = self._create_view(case.case_id)
        case_data = view.walk_through_case_forms(case, subcase_count=0)

        self.assertEqual(case_data['reopened_cases'][0].name, 'other_case')

    # Testing case actions retrieval
    def test_form_touched_cases_walk_returns_correct_actions(self):
        cases, xforms = self.make_simple_case(scenario='simple')
        view = self._create_view(cases['main_case_id'])
        case_actions = view.walk_through_form_touched_cases(cases['main_case_id'],
                                                            list(xforms.keys())[0], subcase_count=0)
        self.assertEqual(case_actions[0].actions, 'create')

    def test_form_touched_cases_walk_returns_correct_update_actions(self):
        cases, xforms = self.make_simple_case(scenario='affected')
        view = self._create_view(cases['main_case_id'])
        form = list(xforms.keys())[2]
        view.form_names[form.form_id] = 'form_name'
        case_actions = view.walk_through_form_touched_cases(cases['main_case_id'], form, subcase_count=0)

        self.assertEqual(case_actions[0].actions, 'update')

    def test_form_touched_cases_walk_returns_correct_close_actions(self):
        cases, xforms = self.make_simple_case(scenario='closed')
        view = self._create_view(cases['main_case_id'])
        form = list(xforms.keys())[2]
        view.form_names[form.form_id] = 'form_name'
        case_actions = view.walk_through_form_touched_cases(cases['main_case_id'], form, subcase_count=0)

        self.assertIn('close', [case_actions[0].actions, case_actions[1].actions])

    # Testing case data retrieval for form driven case deletion
    def test_case_walk_returns_correct_form_delete_case_list(self):
        xform, xform_case = self.make_complex_case(xform_delete=True)
        view = self._create_view(xform_case.case_id, xform.form_id)
        case_data = view.get_cases_and_forms_for_deletion(self.request, self.domain,
                                                          xform_case.case_id, xform.form_id)
        self.assertTrue(case_data['form_delete_cases'][0].name, 'child_2')
        self.assertEqual(case_data['delete_cases'][0].name, 'sub2')

    def test_case_walk_returns_correct_form_delete_affected_list(self):
        xform, xform_case = self.make_complex_case(xform_delete=True)
        view = self._create_view(xform_case.case_id, xform.form_id)
        case_data = view.get_cases_and_forms_for_deletion(self.request, self.domain,
                                                          xform_case.case_id, xform.form_id)
        self.assertEqual(case_data['form_affected_cases'][0].name, 'main_case')

    # Testing deletion
    def test_delete_case(self):
        """
        Ensure that a single case with a single form is soft deleted
        """
        cases, _ = self.make_simple_case(scenario='simple')
        view = self._create_view(cases['main_case_id'])
        delete_dict = view.get_cases_and_forms_for_deletion(self.request, self.domain, cases['main_case_id'])
        soft_delete_cases_and_forms(self.request, self.domain,
                                    delete_dict['case_delete_list'], delete_dict['form_delete_list'])

        case = CommCareCase.objects.get_case(cases['main_case_id'], self.domain)
        self.assertIsNotNone(case.deleted_on)

    def test_delete_submission_forms(self):
        """
        Ensure that for a case with mulitple subcases, each with their own subcases, all related submission
        forms are archived and soft deleted
        """
        cases, _ = self.make_complex_case()
        view = self._create_view(cases['main_case_id'])
        delete_dict = view.get_cases_and_forms_for_deletion(self.request, self.domain, cases['main_case_id'])
        soft_delete_cases_and_forms(self.request, self.domain,
                                    delete_dict['case_delete_list'], delete_dict['form_delete_list'])

        for form in delete_dict['form_delete_list']:
            form = XFormInstance.objects.get_form(form, self.domain)
            self.assertTrue(form.is_archived)
            self.assertIsNotNone(form.deleted_on)

    def test_delete_multiple_related_cases(self):
        """
        Ensure that a case with mulitple subcases, each with their own subcases are all soft deleted
        """
        cases, _ = self.make_complex_case()
        view = self._create_view(cases['main_case_id'])
        delete_dict = view.get_cases_and_forms_for_deletion(self.request, self.domain, cases['main_case_id'])
        soft_delete_cases_and_forms(self.request, self.domain,
                                    delete_dict['case_delete_list'], delete_dict['form_delete_list'])

        for case in delete_dict['case_delete_list']:
            case_obj = CommCareCase.objects.get_case(case, self.domain)
            self.assertIsNotNone(case_obj.deleted_on)

    def test_delete_case_with_form_that_closes_another_case(self):
        """
        Ensure that when a case with a submission form that closed another case is deleted, that other
        case is re-opened. This is really testing form archiving but here for completeness.
        """
        cases, _ = self.make_simple_case(scenario='closed')
        view = self._create_view(cases['main_case_id'])

        other_case = CommCareCase.objects.get_case(cases['other_case_id'], self.domain)
        self.assertTrue(other_case.closed)

        delete_dict = view.get_cases_and_forms_for_deletion(self.request, self.domain, cases['main_case_id'])
        soft_delete_cases_and_forms(self.request, self.domain,
                                    delete_dict['case_delete_list'], delete_dict['form_delete_list'])

        other_case = CommCareCase.objects.get_case(cases['other_case_id'], self.domain)
        self.assertFalse(other_case.closed)

    def test_delete_case_that_updates_another_case(self):
        """
        Ensure that when a case with a submission form that updates another case is deleted, that form doesn't
        appear in the other case's xform_ids. This is really testing form archiving but here for completeness.
        """
        cases, xforms = self.make_simple_case(scenario='affected')
        view = self._create_view(cases['main_case_id'])

        other_case = CommCareCase.objects.get_case(cases['other_case_id'], self.domain)
        self.assertEqual(len(other_case.xform_ids), 2)

        delete_dict = view.get_cases_and_forms_for_deletion(self.request, self.domain, cases['main_case_id'])
        soft_delete_cases_and_forms(self.request, self.domain,
                                    delete_dict['case_delete_list'], delete_dict['form_delete_list'])

        other_case = CommCareCase.objects.get_case(cases['other_case_id'], self.domain)
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
        for i in range(DeleteCaseView.MAX_CASE_COUNT):
            child_case_id = uuid.uuid4().hex
            submit_case_blocks([
                CaseBlock(main_case_id, create=True).as_text(),
                CaseBlock(child_case_id, create=True).as_text(),
            ], self.domain)
        self.addCleanup(_delete_all_cases_and_forms, self.domain)

        view = self._create_view(main_case_id)
        return_dict = view.get_cases_and_forms_for_deletion(request, self.domain, main_case_id)
        self.assertTrue(return_dict['redirect'])

    def test_case_deletion_errors_if_too_many_subcases(self):
        """
        Ensure that a case with 3 or more nested subcases throws an error
        """
        request = deepcopy(self.request)
        setattr(request, 'session', 'session')
        setattr(request, '_messages', FallbackStorage(request))

        cases = [uuid.uuid4().hex for i in range(DeleteCaseView.MAX_SUBCASE_DEPTH + 1)]
        for i in range(DeleteCaseView.MAX_SUBCASE_DEPTH):
            submit_case_blocks([
                CaseBlock(cases[i], create=True).as_text(),
                CaseBlock(cases[i + 1], create=True).as_text(),
            ], self.domain)
        self.addCleanup(_delete_all_cases_and_forms, self.domain)

        view = self._create_view(cases[0])
        return_dict = view.get_cases_and_forms_for_deletion(request, self.domain, cases[0])
        self.assertTrue(return_dict['redirect'])

    def test_case_deletion_redirect_if_case_is_already_deleted(self):
        """
        In the event that a user tries to delete a case after the case has already been deleted, they should
        be redirected.
        """
        request = deepcopy(self.request)
        setattr(request, 'session', 'session')
        setattr(request, '_messages', FallbackStorage(request))

        case = create_case(domain=self.domain, deleted_on=datetime.now(), save=True)
        self.addCleanup(_delete_all_cases_and_forms, self.domain)
        view = self._create_view(case)

        return_dict = view.get_cases_and_forms_for_deletion(request, self.domain, case.case_id)
        self.assertTrue(return_dict['redirect'])
