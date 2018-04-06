# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
import os

from lxml import etree
from django.test import TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import SuiteMixin
from corehq.apps.app_manager.app_translations import escape_output_value

import commcare_translations


class AppManagerTranslationsTest(TestCase, SuiteMixin):
    root = os.path.dirname(__file__)
    file_path = ('data', 'suite')

    def test_escape_output_value(self):
        test_cases = [
            ('hello', '<value>hello</value>'),
            ('abc < def > abc', '<value>abc &lt; def &gt; abc</value>'),
            ("bee's knees", "<value>bee's knees</value>"),
            ('unfortunate <xml expression', '<value>unfortunate &lt;xml expression</value>'),
            ('क्लिक', '<value>&#2325;&#2381;&#2354;&#2367;&#2325;</value>'),
            ('&#39', '<value>&amp;#39</value>'),
            ('question1 is <output value="/data/question1" vellum:value="#form/question1"/> !',
             '<value>question1 is &lt;output value="/data/question1" vellum:value="#form/question1"/&gt; !</value>'),
            ('Here is a ref <output value="/data/no_media"/> with some "trailing" text & that\'s some bad < xml.',
             '<value>Here is a ref &lt;output value="/data/no_media"/&gt; with some "trailing" text &amp; that\'s some bad &lt; xml.</value>')

        ]
        for input, expected_output in test_cases:
            self.assertEqual(expected_output, etree.tostring(escape_output_value(input)))

    def test_language_names(self):
        app_json = self.get_json('app')
        app_json['langs'] = ['en', 'fra', 'hin', 'pol']
        app = Application.wrap(app_json)
        app.create_suite()
        app_strings = app.create_app_strings('default')
        app_strings_dict = commcare_translations.loads(app_strings)
        self.assertEqual(app_strings_dict['en'], 'English')
        self.assertEqual(app_strings_dict['fra'], 'Français')
        self.assertEqual(app_strings_dict['hin'], 'हिंदी')
        self.assertEqual(app_strings_dict['pol'], 'polski')
