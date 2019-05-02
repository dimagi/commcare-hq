from __future__ import absolute_import
from __future__ import unicode_literals

from django.test.testcases import TestCase

import inspect

from django.views.generic.base import View

from custom.icds_reports import views


NON_LOCATION_SAFE_VIEWS = [
    'AggregationScriptPage',
    'BaseDomainView',
    'TemplateView',
    'BugReportView',
    'RedirectView',
    'ICDSBugReportView'
]


class TestInactiveMobileUsers(TestCase):

    def test_get_inactive_users(self):
        for cls_name, cls in inspect.getmembers(views, inspect.isclass):
            if cls_name in NON_LOCATION_SAFE_VIEWS:
                continue

            if issubclass(cls, View) and cls != View:
                assert cls.is_location_safe is True
