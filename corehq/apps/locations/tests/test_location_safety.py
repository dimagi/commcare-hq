from django.views.generic.base import View

from mock import MagicMock

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


def test_view_safety():
    def _assert(view_fn, is_safe):
        assert is_location_safe(view_fn, MagicMock(), (), {}) == is_safe, \
            f"{view_fn} {'IS NOT' if is_safe else 'IS'} marked as location-safe"

    for view, is_safe in [
            (safe_fn_view, True),
            (unsafe_fn_view, False),
            (SafeClsView, True),
            (UnsafeClsView, False),
    ]:
        yield _assert, view, is_safe
