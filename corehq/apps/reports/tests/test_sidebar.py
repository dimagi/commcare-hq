from django.test import SimpleTestCase
from mock import patch, MagicMock

from corehq.apps.reports.models import ReportsSidebarOrdering
from corehq.tabs.tabclasses import ProjectReportsTab
from corehq.tabs.utils import regroup_sidebar_items


class TestReportsTabSidebar(SimpleTestCase):

    def test_custom_reordering(self):
        original_items = [
            ("Custom reports", [
                {"class_name": "foo"},
                {"class_name": "bar"},
            ]),
            ("User reports", [
                {"class_name": "baz"},
                {"class_name": "qux"},
            ]),
        ]

        ordering = [["new section", ["qux", "foo", "dne"]]]
        reordered = regroup_sidebar_items(ordering, original_items)

        self.assertEqual(reordered, [
            ("new section", [
                {"class_name": "qux"},
                {"class_name": "foo"},
            ]),
            ("Custom reports", [
                {"class_name": "bar"},
            ]),
            ("User reports", [
                {"class_name": "baz"},
            ]),
        ])
