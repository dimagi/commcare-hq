from unittest.mock import patch
from django.test import TestCase

from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyGroup,
    CaseType,
)
from corehq.apps.reports.standard.cases.case_data import (
    _get_case_property_tables,
)


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
