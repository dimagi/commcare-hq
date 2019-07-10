from __future__ import absolute_import, unicode_literals

import inspect

from django.views.generic.base import View

from custom.aaa import views

NON_LOCATION_SAFE_VIEWS = [
    'AggregationScriptPage',
    'BaseDomainView',
    'TemplateView',
]


def test_all_views_are_location_safe():
    for cls_name, cls in inspect.getmembers(views, inspect.isclass):
        if cls_name in NON_LOCATION_SAFE_VIEWS:
            continue

        if issubclass(cls, View) and cls != View:
            assert cls.is_location_safe is True
