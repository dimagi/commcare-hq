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

    def test_put_in_root_with_root_module(self):
        root_module = Mock()
        root_module.id = 1
        root_module.put_in_root = False

        module = Mock()
        module.id = 2
        module.put_in_root = True
        module.root_module = root_module

        self.assertEqual(id_strings.menu_id(module), 'm1-m2')

    def test_put_in_root_with_root_module_suffixed(self):
        root_module = Mock()
        root_module.id = 1
        root_module.put_in_root = False

        module = Mock()
        module.id = 2
        module.put_in_root = True
        module.root_module = root_module

        self.assertEqual(id_strings.menu_id(module, suffix='foo'), 'm1-m2.foo')

    def test_put_in_root_nested_suffixed(self):
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

        self.assertEqual(id_strings.menu_id(module, suffix='foo'), 'm1-m2-m3.foo')
