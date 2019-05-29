# coding=utf-8
from __future__ import absolute_import, unicode_literals

import os
from collections import OrderedDict

from django.test import TestCase

from lxml import etree
from testil import eq

import commcare_translations
from corehq.apps.app_manager import app_strings
from corehq.apps.app_manager.models import Application, BuildProfile
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import SuiteMixin
from corehq.apps.translations.app_translations.upload_form import BulkAppTranslationFormUpdater


def get_app():
    app = Application.new_app("test-domain", "Test App")
    app.langs = ["en", "rus"]
    app.set_translation("en", "hello", "Hello")
    app.set_translation("rus", "hello", "привет")
    app.set_translation("en", "goodbye", "Goodbye")
    app.set_translation("rus", "goodbye", "до свидания")
    app.set_translation("en", "all_yr_base", "ALL YOUR BASE ARE BELONG TO US")
    app.set_translation("rus", "all_yr_base", "ВСЯ ВАША БАЗА ОТНОСИТСЯ К НАМ")  # Well, that's what Google says
    return app


def test_get_app_translation_keys():
    app = get_app()
    select_known = app_strings.CHOICES["select-known"]
    keys = select_known.get_app_translation_keys(app)
    eq(keys, {"hello", "goodbye", "all_yr_base"})


def test_non_empty_only():
    things = {
        "none": None,
        "zero": 0,
        "empty": "",
        "empty_too": [],
        "also_empty": {},
        "all_of_the_things": [None, 0, "", [], {}],
    }
    non_empty_things = app_strings.non_empty_only(things)
    eq(non_empty_things, {"all_of_the_things": [None, 0, "", [], {}]})


class AppManagerTranslationsTest(TestCase, SuiteMixin):
    root = os.path.dirname(__file__)

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
            escaped_input = BulkAppTranslationFormUpdater.escape_output_value(input)
            self.assertEqual(expected_output, etree.tostring(escaped_input).decode('utf-8'))

    def test_language_names(self):
        factory = AppFactory(build_version='2.40.0')
        factory.app.langs = ['en', 'fra', 'hin', 'pol']
        factory.app.create_suite()
        app_strings = factory.app.create_app_strings('default')
        app_strings_dict = commcare_translations.loads(app_strings)
        self.assertEqual(app_strings_dict['en'], 'English')
        self.assertEqual(app_strings_dict['fra'], 'Français')
        self.assertEqual(app_strings_dict['hin'], 'हिंदी')
        self.assertEqual(app_strings_dict['pol'], 'polski')

    def _generate_app_strings(self, app, lang, build_profile_id=None):
        content = app.create_app_strings(lang, build_profile_id)
        return {
            line[:line.find('=')]: line[line.find('=') + 1:]
            for line in content.splitlines()
        }

    def test_app_strings(self):
        factory = AppFactory(build_version='2.40.0')
        factory.app.langs = ['en', 'es']
        module, form = factory.new_basic_module('my_module', 'cases')
        module.name = {
            'en': 'Fascination Street',
            'es': 'Calle de Fascinación',
        }
        form.name = {
            'en': 'Prayers for Rain',
            'es': 'Oraciones por la Lluvia',
        }

        en_strings = self._generate_app_strings(factory.app, 'en')
        self.assertEqual(en_strings['modules.m0'], module.name['en'])
        self.assertEqual(en_strings['forms.m0f0'], form.name['en'])

        es_strings = self._generate_app_strings(factory.app, 'es')
        self.assertEqual(es_strings['modules.m0'], module.name['es'])
        self.assertEqual(es_strings['forms.m0f0'], form.name['es'])

        default_strings = self._generate_app_strings(factory.app, 'default')
        self.assertEqual(default_strings['modules.m0'], module.name['en'])
        self.assertEqual(default_strings['forms.m0f0'], form.name['en'])

    def test_default_app_strings_with_build_profiles(self):
        factory = AppFactory(build_version='2.40.0')
        factory.app.langs = ['en', 'es']
        factory.app.build_profiles = OrderedDict({
            'en': BuildProfile(langs=['en'], name='en-profile'),
            'es': BuildProfile(langs=['es'], name='es-profile'),
        })
        module, form = factory.new_basic_module('my_module', 'cases')
        module.name = {
            'en': 'Alive',
            'es': 'Viva',
        }
        form.name = {
            'en': 'Human',
            'es': 'Humana',
        }

        all_default_strings = self._generate_app_strings(factory.app, 'default')
        self.assertEqual(all_default_strings['modules.m0'], module.name['en'])
        self.assertEqual(all_default_strings['forms.m0f0'], form.name['en'])

        en_default_strings = self._generate_app_strings(factory.app, 'default', build_profile_id='en')
        self.assertEqual(en_default_strings['modules.m0'], module.name['en'])
        self.assertEqual(en_default_strings['forms.m0f0'], form.name['en'])

        es_default_strings = self._generate_app_strings(factory.app, 'default', build_profile_id='es')
        self.assertEqual(es_default_strings['modules.m0'], module.name['es'])
        self.assertEqual(es_default_strings['forms.m0f0'], form.name['es'])
