from django.test import SimpleTestCase
from mock import patch, MagicMock

from corehq.apps.reports.models import ReportsSidebarOrdering
from corehq.tabs.tabclasses import ProjectReportsTab


class TestReportsTabSidebar(SimpleTestCase):

    def test_custom_reordering(self):
        tab = ProjectReportsTab(None)
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

        mock_ordering = ReportsSidebarOrdering(
            domain="wut",
            config=[
                ["new section", ["qux", "foo", "dne"]]
            ],
        )
        def mock_get(*args, **kwargs):
            return mock_ordering
        mock_class = MagicMock(objects=MagicMock(get=mock_get))

        with patch("corehq.tabs.tabclasses.ReportsSidebarOrdering", new=mock_class):
            reordered = tab._regroup_sidebar_items(original_items)
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
