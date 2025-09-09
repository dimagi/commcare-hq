from django.views.generic.base import View

import pytest
from unittest.mock import MagicMock

from corehq.apps.reports.dispatcher import ReportDispatcher
from corehq.apps.reports.generic import GenericReportView

from ..permissions import conditionally_location_safe, is_location_safe, location_safe


@location_safe
def safe_fn_view(request, domain):
    return "hello"


def unsafe_fn_view(request, domain):
    return "hello"


@location_safe
class SafeClsView(View):
    pass


class UnsafeClsView(View):
    pass


class ImplicitlySafeChildOfSafeClsView(SafeClsView):
    """This inherits its parent class's safety"""


@location_safe
class SafeChildofUnsafeClsView(UnsafeClsView):
    """This shouldn't hoist its safety up to the parent class"""


@pytest.mark.parametrize("view_fn, is_safe", [
    (safe_fn_view, True),
    (unsafe_fn_view, False),
    (SafeClsView.as_view(), True),
    (UnsafeClsView.as_view(), False),
    (ImplicitlySafeChildOfSafeClsView.as_view(), True),
    (SafeChildofUnsafeClsView.as_view(), True),
])
def test_django_view_safety(view_fn, is_safe):
    assert is_location_safe(view_fn, MagicMock(), (), {}) == is_safe, \
        f"{view_fn} {'IS NOT' if is_safe else 'IS'} marked as location-safe"


def _sometimes_safe(view_fn, request, *args, **kwargs):
    return request.this_is_safe


@conditionally_location_safe(_sometimes_safe)
def conditionally_safe_fn_view(request, domain):
    return "hello"


@conditionally_location_safe(_sometimes_safe)
class ConditionallySafeClsView(View):
    pass


class ImplicitlySafeChildOfConditionallySafeClsView(ConditionallySafeClsView):
    pass


@pytest.mark.parametrize("view_fn, is_safe", [
    (conditionally_safe_fn_view, True),
    (ConditionallySafeClsView.as_view(), True),
    (ImplicitlySafeChildOfConditionallySafeClsView.as_view(), True),
    (conditionally_safe_fn_view, False),
    (ConditionallySafeClsView.as_view(), False),
    (ImplicitlySafeChildOfConditionallySafeClsView.as_view(), False),
])
def test_conditionally_safe_django_views(view_fn, is_safe):
    request = MagicMock(this_is_safe=is_safe)
    assert is_location_safe(view_fn, request, (), {}) == is_safe, \
        f"{view_fn} {'IS NOT' if is_safe else 'IS'} marked as location-safe"


class ExampleReportDispatcher(ReportDispatcher):
    @classmethod
    def get_reports(cls, domain):
        return [('All Reports', [
            SafeHQReport,
            UnsafeHQReport,
            ImplicitlySafeChildOfSafeHQReport,
            SafeChildOfUnsafeHQReport,
            ConditionallySafeHQReport,
        ])]


class BaseReport(GenericReportView):
    dispatcher = ExampleReportDispatcher


@location_safe
class SafeHQReport(BaseReport):
    slug = 'safe_hq_report'


class UnsafeHQReport(BaseReport):
    slug = 'unsafe_hq_report'


class ImplicitlySafeChildOfSafeHQReport(SafeHQReport):
    """This inherits safety from its parent"""
    slug = 'implicitly_safe_child_of_safe_hq_report'


@location_safe
class SafeChildOfUnsafeHQReport(UnsafeHQReport):
    slug = 'safe_child_of_unsafe_hq_report'


@conditionally_location_safe(_sometimes_safe)
class ConditionallySafeHQReport(BaseReport):
    slug = 'conditionally_safe_hq_report'


@pytest.mark.parametrize("report, request_, is_safe", [
    (SafeHQReport, MagicMock(), True),
    (UnsafeHQReport, MagicMock(), False),
    (ImplicitlySafeChildOfSafeHQReport, MagicMock(), True),
    (SafeChildOfUnsafeHQReport, MagicMock(), True),
    (ConditionallySafeHQReport, MagicMock(this_is_safe=True), True),
    (ConditionallySafeHQReport, MagicMock(this_is_safe=False), False),
])
def test_hq_report_safety(report, request_, is_safe):
    view_fn = report.dispatcher.as_view()
    view_kwargs = {'domain': 'foo', 'report_slug': report.slug}
    assert is_location_safe(view_fn, request_, (), view_kwargs) == is_safe, \
        f"{report} {'IS NOT' if is_safe else 'IS'} marked as location-safe"
