from unittest.mock import Mock

from django.test import TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.views.apps import get_app_view_context
from corehq.apps.domain.shortcuts import create_domain


class GetAppViewContextTests(TestCase):

    def setUp(self):
        self.domain = create_domain('test')
        self.app = Application(domain=self.domain.name, langs=['en'])

    def test_bulk_translation_forms(self):
        request = Mock()
        context = get_app_view_context(request, self.app)
        # ensure form actions are the same as what is in the context data
        app_form = context['bulk_app_translation_form']
        ui_form = context['bulk_ui_translation_form']
        assert ui_form.helper.form_action == context['bulk_ui_translation_upload']['action']
        assert app_form.helper.form_action == context['bulk_app_translation_upload']['action']
