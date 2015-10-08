from django.test import override_settings, SimpleTestCase
from pillowtop import get_all_pillow_instances, get_all_pillow_classes, get_pillow_by_name
from pillowtop.listener import BasicPillow
from inspect import isclass


@override_settings(PILLOWTOPS={'test': ['pillowtop.tests.FakePillow']})
class PillowTopTestCase(SimpleTestCase):

    def test_import_pillows_class_only(self):
        pillows = get_all_pillow_classes()
        self.assertEquals(len(pillows), 1)
        self.assertTrue(isclass(pillows[0]))

    def test_import_pillows(self):
        pillows = get_all_pillow_instances()
        self.assertEquals(len(pillows), 1)
        self.assertFalse(isclass(pillows[0]))

    def test_get_pillow_by_name(self):
        self.assertEqual(FakePillow, type(get_pillow_by_name('FakePillow')))


class FakePillow(BasicPillow):
    pass
