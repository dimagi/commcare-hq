from django.views.generic.base import View

from mock import MagicMock

from corehq.apps.reports.dispatcher import ReportDispatcher
from corehq.apps.reports.generic import GenericReportView

from ..permissions import is_location_safe, location_safe


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


class UnSafeChildOfSafeClsView(SafeClsView):
    """This inherits its parent class's safety"""  # TODO change this behavior


@location_safe
class SafeChildofUnsafeClsView(UnsafeClsView):
    """This shouldn't hoist its safety up to the parent class"""


def test_django_view_safety():
    def _assert(view_fn, is_safe):
        assert is_location_safe(view_fn, MagicMock(), (), {}) == is_safe, \
            f"{view_fn} {'IS NOT' if is_safe else 'IS'} marked as location-safe"

    for view, is_safe in [
            (safe_fn_view, True),
            (unsafe_fn_view, False),
            (SafeClsView.as_view(), True),
            (UnsafeClsView.as_view(), False),
            (UnSafeChildOfSafeClsView.as_view(), True),
            (SafeChildofUnsafeClsView.as_view(), True),
    ]:
        yield _assert, view, is_safe


class ExampleReportDispatcher(ReportDispatcher):
    @classmethod
    def get_reports(cls, domain):
        return [('All Reports', [r for r, is_safe in EXAMPLE_REPORTS])]


class BaseReport(GenericReportView):
    dispatcher = ExampleReportDispatcher


@location_safe
class SafeHQReport(BaseReport):
    slug = 'safe_hq_report'


class UnsafeHQReport(BaseReport):
    slug = 'unsafe_hq_report'


class UnsafeChildOfSafeHQReport(SafeHQReport):
    slug = 'unsafe_child_of_safe_hq_report'


@location_safe
class SafeChildOfUnsafeHQReport(UnsafeHQReport):
    slug = 'safe_child_of_unsafe_hq_report'


EXAMPLE_REPORTS = [
    (SafeHQReport, True),
    (UnsafeHQReport, False),
    (UnsafeChildOfSafeHQReport, False),
    (SafeChildOfUnsafeHQReport, True),
]


def test_hq_report_safety():
    for report, is_safe in EXAMPLE_REPORTS:
        def _assert(report, is_safe):
            view_fn = report.dispatcher.as_view()
            view_kwargs = {'domain': 'foo', 'report_slug': report.slug}
            assert is_location_safe(view_fn, MagicMock(), (), view_kwargs) == is_safe, \
                f"{report} {'IS NOT' if is_safe else 'IS'} marked as location-safe"

        yield _assert, report, is_safe
