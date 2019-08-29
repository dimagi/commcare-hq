
from django.test import TestCase

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.domain.models import Domain


class DomainCopyTest(TestCase):

    def setUp(self):
        self.domain = Domain(name='test')
        self.domain.save()
        app = Application.new_app('test', "Test Application", lang='en')
        module = Module.new_module("Untitled Module", 'en')
        app.add_module(module)
        app.new_form(0, "Untitled Form", 'en')
        app.save()

    def tearDown(self):
        self.domain.delete()

    def test_base(self):
        new_domain = self.domain.save_copy()
        new_domain.delete()

    def test_usercase_enabled(self):
        self.domain.usercase_enabled = True
        self.domain.save()
        new_domain = self.domain.save_copy()
        new_domain.delete()
