# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestXmlMixin


class SuiteFormatsTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def _test_format(self, detail_format, template_form):
        app = Application.wrap(self.get_json('app_audio_format'))
        details = app.get_module(0).case_details
        details.short.get_column(0).format = detail_format
        details.long.get_column(0).format = detail_format

        expected = """
        <partial>
          <template form="{0}">
            <text>
              <xpath function="picproperty"/>
            </text>
          </template>
          <template form="{0}">
            <text>
              <xpath function="picproperty"/>
            </text>
          </template>
        </partial>
        """.format(template_form)
        self.assertXmlPartialEqual(expected, app.create_suite(), "./detail/field/template")

    def test_audio_format(self):
        self._test_format('audio', 'audio')

    def test_image_format(self):
        self._test_format('picture', 'image')
