from django.test import SimpleTestCase
from dimagi.utils.modules import to_function


class ModulesTests(SimpleTestCase):

    def test_to_function_simple(self):
        fn = to_function('dimagi.utils.modules.to_function', failhard=True)
        self.assertIsNotNone(fn)
        self.assertEqual(fn, to_function)

    def test_to_function_unicode(self):
        fn = to_function('dimagi.utils.modules.to_function', failhard=True)
        self.assertIsNotNone(fn)
        self.assertEqual(fn, to_function)

    def test_to_function_package_level(self):
        cls = to_function('dimagi.utils.tests.test_modules.ModulesTests', failhard=True)
        self.assertIsNotNone(cls)
        self.assertEqual(cls, ModulesTests)


