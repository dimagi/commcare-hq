from django.test import RequestFactory, SimpleTestCase

from corehq.apps.hqwebapp import decorators
from corehq.apps.hqwebapp.utils.bootstrap import BOOTSTRAP_3, BOOTSTRAP_5, get_bootstrap_version, \
    set_bootstrap_version3
from corehq.util.test_utils import generate_cases
from inspect import getmembers, isfunction


def filter_decorators(obj):
    return isfunction(obj) and obj.__name__.startswith("use_") and obj.__name__ != "use_bootstrap5"


ALL_DECORATORS = [member[1] for member in getmembers(decorators, filter_decorators)]


class TestDecorators(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_use_bootstrap5(self):
        @decorators.use_bootstrap5
        def dummy_view(request):
            self.assertEqual(get_bootstrap_version(), BOOTSTRAP_5)

        set_bootstrap_version3()
        self.assertEqual(get_bootstrap_version(), BOOTSTRAP_3)
        dummy_view(self.factory.get('/'))

    @generate_cases([
        (decorator,) for decorator in ALL_DECORATORS
    ])
    def test_flag_decorators__function_view(self, decorator):
        def dummy_view(request):
            return True

        request = self.factory.get('/')
        decorator(dummy_view)(request)
        self.assertTrue(getattr(request, decorator.__name__))

    @generate_cases([
        (decorator,) for decorator in ALL_DECORATORS
    ])
    def test_flag_decorators__cls_view(self, decorator):
        request = self.factory.get('/')
        decorator(self._dummy_cls_view)(request)
        self.assertTrue(getattr(request, decorator.__name__))

    def _dummy_cls_view(self, request):
        return True
