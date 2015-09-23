from django.test import override_settings, SimpleTestCase
from pillowtop import get_all_pillows
from pillowtop.listener import BasicPillow
from inspect import isclass


@override_settings(PILLOWTOPS={'test': ['pillowtop.tests.FakePillow']})
class PillowTopTestCase(SimpleTestCase):

    def test_import_pillows_class_only(self):
        pillows = get_all_pillows(instantiate=False)
        self.assertEquals(len(pillows), 1)
        self.assertTrue(isclass(pillows[0]))

    def test_import_pillows(self):
        pillows = get_all_pillows(instantiate=True)
        self.assertEquals(len(pillows), 1)
        self.assertFalse(isclass(pillows[0]))


class FakePillow(BasicPillow):
    pass
