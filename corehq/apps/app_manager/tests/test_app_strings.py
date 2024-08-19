import os
from collections import OrderedDict

from django.test import TestCase

import commcare_translations
from lxml import etree
from testil import eq

from corehq.apps.app_manager import app_strings
from corehq.apps.app_manager.models import (
    Application,
    BuildProfile,
    CaseSearch,
    CaseSearchAgainLabel,
    CaseSearchLabel,
    CaseSearchProperty,
    MappingItem,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import SuiteMixin
from corehq.apps.translations.app_translations.upload_form import (
    BulkAppTranslationFormUpdater,
)
from corehq.util.test_utils import flag_enabled, flag_disabled


def get_app():
    app = Application.new_app("test-domain", "Test App")
    app.langs = ["en", "rus"]
    app.set_translations("en", {
        "hello": "Hello",
        "goodbye": "Goodbye",
        "all_yr_base": "ALL YOUR BASE ARE BELONG TO US",
    })
    app.set_translations("rus", {
        "hello": "привет",
        "goodbye": "до свидания",
        "all_yr_base": "ВСЯ ВАША БАЗА ОТНОСИТСЯ К НАМ",  # Well, that's what Google says
    })
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
            ('क्लिक', '<value>क्लिक</value>'),
            ('&#39', '<value>&amp;#39</value>'),
            ('question1 is <output value="/data/question1" vellum:value="#form/question1"/> !',
             '<value>question1 is &lt;output value="/data/question1" '
             'vellum:value="#form/question1"/&gt; !</value>'),
            ('Here is a ref <output value="/data/no_media"/> with some "trailing" text & that\'s some bad < xml.',
             '<value>Here is a ref &lt;output value="/data/no_media"/&gt; with some "trailing" text &amp; that\'s'
             ' some bad &lt; xml.</value>')

        ]
        for input, expected_output in test_cases:
            escaped_input = BulkAppTranslationFormUpdater.escape_output_value(input)
            self.assertEqual(expected_output, etree.tostring(escaped_input, encoding='utf-8').decode('utf-8'))

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

    def test_modules_case_search_app_strings(self):
        factory = AppFactory(build_version='2.40.0')
        factory.app.langs = ['en', 'es']
        factory.app.build_profiles = OrderedDict({
            'en': BuildProfile(langs=['en'], name='en-profile'),
            'es': BuildProfile(langs=['es'], name='es-profile'),
        })
        module, form = factory.new_basic_module('my_module', 'cases')
        module.search_config = CaseSearch(
            search_label=CaseSearchLabel(
                label={'en': 'Get them', 'es': 'Conseguirlos'},
                media_image={
                    'en': "jr://file/commcare/image/1.png",
                    'es': "jr://file/commcare/image/1_es.png"
                },
                media_audio={'en': "jr://file/commcare/image/2.mp3"}
            ),
            search_again_label=CaseSearchAgainLabel(
                label={'en': 'Get them all'}
            ),
            properties=[
                CaseSearchProperty(is_group=True, name='group_header_0',
                                   group_key='group_header_0', label={'en': 'Personal Information'}),
                CaseSearchProperty(name="name", label={'en': 'Name'})
            ]
        )
        # wrap to have assign_references called
        app = Application.wrap(factory.app.to_json())

        with flag_disabled('USH_CASE_CLAIM_UPDATES'):
            # default language
            self.assertEqual(app.default_language, 'en')
            en_app_strings = self._generate_app_strings(app, 'default', build_profile_id='en')
            self.assertEqual(en_app_strings['case_search.m0'], 'Search All Cases')
            self.assertEqual(en_app_strings['case_search.m0.again'], 'Search Again')
            self.assertFalse('case_search.m0.icon' in en_app_strings)
            self.assertFalse('case_search.m0.audio' in en_app_strings)

            # non-default language
            es_app_strings = self._generate_app_strings(app, 'es', build_profile_id='es')
            self.assertEqual(es_app_strings['case_search.m0'], 'Search All Cases')
            self.assertEqual(es_app_strings['case_search.m0.again'], 'Search Again')

        with flag_enabled('USH_CASE_CLAIM_UPDATES'):
            # default language
            en_app_strings = self._generate_app_strings(app, 'default', build_profile_id='en')
            self.assertEqual(en_app_strings['case_search.m0'], 'Get them')
            self.assertEqual(en_app_strings['case_search.m0.icon'], 'jr://file/commcare/image/1.png')
            self.assertEqual(en_app_strings['case_search.m0.audio'], 'jr://file/commcare/image/2.mp3')
            self.assertEqual(en_app_strings['case_search.m0.again'], 'Get them all')
            self.assertEqual(en_app_strings['search_property.m0.name'], 'Name')
            self.assertEqual(en_app_strings['search_property.m0.group_header_0'], 'Personal Information')

            # non-default language
            es_app_strings = self._generate_app_strings(app, 'es', build_profile_id='es')
            self.assertEqual(es_app_strings['case_search.m0'], 'Conseguirlos')
            self.assertEqual(es_app_strings['case_search.m0.icon'], 'jr://file/commcare/image/1_es.png')
            self.assertEqual(es_app_strings['case_search.m0.again'], 'Get them all')

    def test_dependencies_app_strings(self):
        app_id = 'callout.commcare.org.sendussd'
        app_name = 'CommCare USSD'

        factory = AppFactory(build_version='2.40.0')
        factory.app.profile['features'] = {'dependencies': [app_id]}

        with flag_disabled('APP_DEPENDENCIES'):
            default_strings = self._generate_app_strings(factory.app, 'default')
            self.assertNotIn(f'android.package.name.{app_id}', default_strings)

        with flag_enabled('APP_DEPENDENCIES'):
            default_strings = self._generate_app_strings(factory.app, 'default')
            self.assertEqual(
                default_strings[f'android.package.name.{app_id}'],
                app_name
            )

    def test_no_items_text_app_strings(self):
        factory = AppFactory(build_version='2.54.0')
        factory.app.langs = ['en', 'es']
        factory.app.build_profiles = OrderedDict({
            'en': BuildProfile(langs=['en'], name='en-profile'),
            'es': BuildProfile(langs=['es'], name='es-profile'),
        })
        module, form = factory.new_basic_module('my_module', 'cases')
        module.case_details.short.no_items_text = {'en': 'Empty List.', 'es': 'Lista Vacía.'}

        # wrap to have assign_references called
        app = Application.wrap(factory.app.to_json())

        with flag_enabled('USH_EMPTY_CASE_LIST_TEXT'):
            # default language
            en_app_strings = self._generate_app_strings(app, 'default', build_profile_id='en')
            self.assertEqual(en_app_strings['m0_no_items_text'], 'Empty List.')

            # non-default language
            es_app_strings = self._generate_app_strings(app, 'es', build_profile_id='es')
            self.assertEqual(es_app_strings['m0_no_items_text'], 'Lista Vacía.')

        factory.new_report_module('my_module')
        app = Application.wrap(factory.app.to_json())

        with flag_enabled('USH_EMPTY_CASE_LIST_TEXT'):
            try:
                en_app_strings = self._generate_app_strings(app, 'default', build_profile_id='en')
            except AttributeError:
                self.fail("_generate_app_strings raised AttributeError unexpectedly")

    def test_form_submit_label(self):
        factory = AppFactory(build_version='2.40.0')
        factory.app.langs = ['en', 'es']
        module, form = factory.new_basic_module('my_module', 'cases')
        form.submit_label = {
            'en': 'Submit Button',
            'es': 'Botón de Enviar',
        }
        form.submit_notification_label = {
            'en': 'You submitted the form!',
            'es': '¡Enviaste el formulario!',
        }
        en_strings = self._generate_app_strings(factory.app, 'en')
        self.assertEqual(en_strings['forms.m0f0.submit_label'], form.submit_label['en'])
        self.assertEqual(en_strings['forms.m0f0.submit_notification_label'], form.submit_notification_label['en'])

        es_strings = self._generate_app_strings(factory.app, 'es')
        self.assertEqual(es_strings['forms.m0f0.submit_label'], form.submit_label['es'])
        self.assertEqual(es_strings['forms.m0f0.submit_notification_label'], form.submit_notification_label['es'])

        default_strings = self._generate_app_strings(factory.app, 'default')
        self.assertEqual(default_strings['forms.m0f0.submit_label'], form.submit_label['en'])
        self.assertEqual(default_strings['forms.m0f0.submit_notification_label'],
                         form.submit_notification_label['en'])

    def test_select_text_app_strings(self):
        factory = AppFactory(build_version='2.54.0')
        factory.app.langs = ['en', 'fra']
        factory.app.build_profiles = OrderedDict({
            'en': BuildProfile(langs=['en'], name='en-profile'),
            'fra': BuildProfile(langs=['fra'], name='fra-profile'),
        })
        module, form = factory.new_basic_module('my_module', 'cases')
        module.case_details.short.select_text = {'en': 'Continue with case', 'fra': 'Continuer avec le cas'}

        app = Application.wrap(factory.app.to_json())

        en_app_strings = self._generate_app_strings(app, 'default', build_profile_id='en')
        self.assertEqual(en_app_strings['m0_select_text'], 'Continue with case')

        es_app_strings = self._generate_app_strings(app, 'fra', build_profile_id='fra')
        self.assertEqual(es_app_strings['m0_select_text'], 'Continuer avec le cas')

    def test_alt_text_app_strings(self):
        factory = AppFactory(build_version='2.54.0')
        factory.app.langs = ['en', 'fra']
        factory.app.build_profiles = OrderedDict({
            'en': BuildProfile(langs=['en'], name='en-profile'),
            'fra': BuildProfile(langs=['fra'], name='fra-profile'),
        })
        module, form = factory.new_basic_module('my_module', 'cases')

        short_column = module.case_details.short.get_column(0)
        short_column.format = 'clickable-icon'
        short_column.model = 'case'
        short_column.field = 'is_favorite'
        short_column.enum = [
            MappingItem(
                key='true',
                value={
                    'en': 'jr://image_is_favorite.png',
                    'fra': 'jr://image_is_favorite.png',
                },
                alt_text={
                    'en': 'filled yellow star',
                    'fra': 'étoile jaune remplie',
                }
            ),
        ]

        app = Application.wrap(factory.app.to_json())

        en_app_strings = self._generate_app_strings(app, 'default', build_profile_id='en')
        self.assertEqual(en_app_strings['m0.case_short.case_is_favorite_1.alt_text.ktrue'], 'filled yellow star')

        fra_app_strings = self._generate_app_strings(app, 'fra', build_profile_id='fra')
        self.assertEqual(fra_app_strings['m0.case_short.case_is_favorite_1.alt_text.ktrue'],
                         'étoile jaune remplie')
