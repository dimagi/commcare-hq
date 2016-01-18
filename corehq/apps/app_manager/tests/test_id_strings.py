from __future__ import unicode_literals
from django.test import SimpleTestCase
from mock import Mock
from corehq.apps.app_manager import id_strings


class MenuIdTests(SimpleTestCase):

    def test_normal_module(self):
        module = Mock()
        module.id = 1
        module.put_in_root = False
        self.assertEqual(id_strings.menu_id(module), 'm1')

    def test_normal_module_suffixed(self):
        module = Mock()
        module.id = 1
        module.put_in_root = False
        self.assertEqual(id_strings.menu_id(module, suffix='foo'), 'm1.foo')

    def test_put_in_root_without_root_module(self):
        module = Mock()
        module.id = 1
        module.put_in_root = True
        module.root_module = None
        self.assertEqual(id_strings.menu_id(module), 'root')

    def get_root_and_module(self):
        root_module = Mock()
        root_module.id = 1
        root_module.put_in_root = False
        root_module.root_module = None

        module = Mock()
        module.id = 2
        module.put_in_root = True
        module.root_module = root_module

        return root_module, module

    def test_put_in_root_with_root_module(self):
        _, module = self.get_root_and_module()
        self.assertEqual(id_strings.menu_id(module), 'm1.m2')

    def test_put_in_root_with_root_module_suffixed(self):
        _, module = self.get_root_and_module()
        self.assertEqual(id_strings.menu_id(module, suffix='foo'), 'm1.m2.foo')

    def get_nested_module(self):
        root_root_module = Mock()
        root_root_module.id = 1
        root_root_module.put_in_root = False

        root_module = Mock()
        root_module.id = 2
        root_module.put_in_root = True
        root_module.root_module = root_root_module

        module = Mock()
        module.id = 3
        module.put_in_root = True
        module.root_module = root_module

        return module

    def test_put_in_root_nested_suffixed(self):
        module = self.get_nested_module()
        self.assertEqual(id_strings.menu_id(module, suffix='foo'), 'm1.m2.m3.foo')

    def test_put_in_root_nested_without_root_module(self):
        module = self.get_nested_module()
        module.root_module.root_module = None  # This makes the ID "root". It should cascade.
        self.assertEqual(id_strings.menu_id(module), 'root')

    def test_put_in_root_nested_without_root_module_suffixed(self):
        module = self.get_nested_module()
        module.root_module.root_module = None
        self.assertEqual(id_strings.menu_id(module, suffix='foo'), 'root')  # Suffix should be ignored

    def test_put_in_root_with_shadow_module(self):
        root_module, module = self.get_root_and_module()

        shadow_module = Mock()
        shadow_module.id = 3
        shadow_module.source_module = root_module
        shadow_module.put_in_root = True
        shadow_module.root_module = shadow_module.source_module.root_module  # Mock what shadow modules do

        self.assertEqual(id_strings.menu_id(shadow_module), 'root')

    def test_put_in_root_with_nested_shadow_module(self):
        _, module = self.get_root_and_module()

        shadow_module = Mock()
        shadow_module.id = 3
        shadow_module.source_module = module
        shadow_module.put_in_root = True
        shadow_module.root_module = shadow_module.source_module.root_module

        self.assertEqual(id_strings.menu_id(shadow_module), 'm1.m3')
