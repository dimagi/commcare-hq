from django.test import TestCase
from corehq.apps.users.models import Permissions


class PermissionsTest(TestCase):

    def test_OR(self):
        p1 = Permissions(
            edit_web_users=True,
            view_reports=True,
            view_report_list=['report1'],
        )
        p2 = Permissions(
            edit_apps=True,
            view_reports=True,
            view_report_list=['report2'],
        )
        self.assertEqual(dict(p1 | p2), dict(Permissions(
            edit_apps=True,
            edit_web_users=True,
            view_reports=True,
            view_report_list=['report1', 'report2'],
        )))
