# encoding: utf-8
import inspect
from django.test import SimpleTestCase
from dimagi.utils.modules import to_function


class ModulesTests(SimpleTestCase):

    def test_to_function_simple(self):
        fn = to_function('dimagi.utils.modules.to_function', failhard=True)
        self.assertIsNotNone(fn)
        self.assertTrue(inspect.isfunction(fn))

    def test_to_function_unicode(self):
        fn = to_function(u'dimagi.utils.modules.to_function', failhard=True)
        self.assertIsNotNone(fn)
        self.assertTrue(inspect.isfunction(fn))

    def test_to_function_package_level(self):
        fn = to_function(u'dimagi.utils.tests.ModulesTests', failhard=True)
        self.assertIsNotNone(fn)
        self.assertTrue(inspect.isfunction(fn))


