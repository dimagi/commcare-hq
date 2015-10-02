from copy import deepcopy
from django.test import SimpleTestCase
from django.test.utils import override_settings
from lxml import etree

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module, ReportModule, ReportAppConfig
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.builds.models import BuildSpec
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio

import commcare_translations


class MediaSuiteTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def test_all_media_paths(self):
        image_path = 'jr://file/commcare/image{}.jpg'
        audio_path = 'jr://file/commcare/audio{}.mp3'
        app = Application.wrap(self.get_json('app'))

        app.get_module(0).case_list.show = True
        app.get_module(0).case_list.set_icon('en', image_path.format('4'))
        app.get_module(0).case_list.set_audio('en', audio_path.format('4'))

        app.get_module(0).set_icon('en', image_path.format('1'))
        app.get_module(0).set_audio('en', audio_path.format('1'))

        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id
        app.get_module(0).case_list_form.set_icon('en', image_path.format('2'))
        app.get_module(0).case_list_form.set_audio('en', audio_path.format('2'))

        app.get_module(0).get_form(0).set_icon('en', image_path.format('3'))
        app.get_module(0).get_form(0).set_audio('en', audio_path.format('3'))

        should_contain_media = [image_path.format(num) for num in [1, 2, 3, 4]] + \
                               [audio_path.format(num) for num in [1, 2, 3, 4]]
        self.assertTrue(app.get_module(0).uses_media())
        self.assertEqual(app.all_media_paths, set(should_contain_media))

    @override_settings(BASE_ADDRESS='192.cc.hq.1')
    def test_case_list_media(self):
        app = Application.wrap(self.get_json('app'))
        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id

        image_path = 'jr://file/commcare/case_list_image.jpg'
        audo_path = 'jr://file/commcare/case_list_audo.mp3'
        app.get_module(0).case_list_form.set_icon('en', image_path)
        app.get_module(0).case_list_form.set_audio('en', audo_path)

        app.create_mapping(CommCareImage(_id='123'), image_path, save=False)
        app.create_mapping(CommCareAudio(_id='456'), audo_path, save=False)

        app.set_media_versions(previous_version=None)

        self.assertXmlEqual(self.get_xml('media_suite'), app.create_media_suite())

    def test_update_image_id(self):
        """
        When an image is updated, change only version number, not resource id
        """
        app = Application.wrap(self.get_json('app'))
        image_path = 'jr://file/commcare/case_list_image.jpg'
        app.get_module(0).case_list_form.set_icon('en', image_path)

        app.version = 1
        app.create_mapping(CommCareImage(_id='123'), image_path, save=False)
        app.set_media_versions(previous_version=None)
        old_app = deepcopy(app)

        app.version = 2
        app.create_mapping(CommCareImage(_id='456'), image_path, save=False)
        app.set_media_versions(previous_version=old_app)

        old_image = old_app.multimedia_map[image_path]
        new_image = app.multimedia_map[image_path]
        self.assertEqual(old_image.unique_id, new_image.unique_id)
        self.assertNotEqual(old_image.version, new_image.version)

    def test_all_media_report_module(self):
        """
        Report Modules don't support media
        """
        from corehq.apps.userreports.tests import get_sample_report_config

        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)

        report_module = app.add_module(ReportModule.new_module('Reports', None))
        report_module.unique_id = 'report_module'
        report = get_sample_report_config()
        report._id = 'd3ff18cd83adf4550b35db8d391f6008'

        report_app_config = ReportAppConfig(report_id=report._id,
                                            header={'en': 'CommBugz'})
        report_app_config._report = report
        report_module.report_configs = [report_app_config]
        report_module._loaded = True

        image_path = 'jr://file/commcare/case_list_image.jpg'
        audio_path = 'jr://file/commcare/case_list_audo.mp3'
        app.get_module(0).case_list_form.set_icon('en', image_path)
        app.get_module(0).case_list_form.set_audio('en', audio_path)

        self.assertFalse(app.get_module(0).uses_media())
        self.assertEqual(len(app.all_media), 0)


class LocalizedMediaSuiteTest(SimpleTestCase, TestXmlMixin):
    """
        For CC >= 2.21
        Tests following for form, module, case_list_menu, case_list_form
        - suite.xml should contain correct localized media references
        - app_strings should contain all of above media references
        - translations should be correct for each of above app_strings
    """
    file_path = ('data', 'suite')
    image_path = 'jr://file/commcare/case_list_image.jpg'
    audio_path = 'jr://file/commcare/case_list_audo.mp3'
    hindi_image = 'jr://file/commcare/case_list_image_hin.jpg'
    hindi_audio = 'jr://file/commcare/case_list_audo_hin.mp3'

    def setUp(self):
        self.app = Application.new_app('domain', "my app", application_version=APP_V2)
        self.module = self.app.add_module(Module.new_module("Module 1", None))
        self.form = self.app.new_form(0, "Form 1", None)
        self.min_spec = BuildSpec.from_string('2.21/latest')
        self.app.build_spec = self.min_spec

    def makeXML(self, menu_locale_id, image_locale_id, audio_locale_id):
        XML_template = """
        <partial>
            <display>
                <text>
                    <locale id="{menu_locale_id}"/>
                </text>
                <text form="image">
                    <locale id="{image_locale_id}"/>
                </text>
                <text form="audio">
                    <locale id="{audio_locale_id}"/>
                </text>
            </display>
        </partial>
        """
        return XML_template.format(
            menu_locale_id=menu_locale_id,
            image_locale_id=image_locale_id,
            audio_locale_id=audio_locale_id,
        )

    def XML_without_media(self, menu_locale_id, for_action_menu=False):
        if for_action_menu:
            XML_template = """
            <partial>
                <display>
                    <text>
                        <locale id="{menu_locale_id}"/>
                    </text>
                </display>
            </partial>
            """
        else:
            XML_template = """
            <partial>
                <text>
                    <locale id="{menu_locale_id}"/>
                </text>
            </partial>
            """

        return XML_template.format(
            menu_locale_id=menu_locale_id,
        )

    def test_form_suite(self):
        no_media_xml = self.XML_without_media("forms.m0f0")
        self.assertXmlPartialEqual(no_media_xml, self.app.create_suite(), "./entry/command[@id='m0-f0']/text")

        self.form.set_icon('en', self.image_path)
        self.form.set_audio('en', self.audio_path)

        XML = self.makeXML("forms.m0f0", "forms.m0f0.icon", "forms.m0f0.audio")
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./entry/command[@id='m0-f0']/display")

        self._assert_app_strings_available(self.app, 'en')

        icon_locale = id_strings.form_icon_locale(self.form)
        audio_locale = id_strings.form_audio_locale(self.form)
        self._test_correct_icon_translations(self.app, self.form, icon_locale)
        self._test_correct_audio_translations(self.app, self.form, audio_locale)

    def test_module_suite(self):
        no_media_xml = self.XML_without_media("modules.m0")
        self.assertXmlPartialEqual(no_media_xml, self.app.create_suite(), "././menu[@id='m0']/text")

        self.module.set_icon('en', self.image_path)
        self.module.set_audio('en', self.audio_path)

        XML = self.makeXML("modules.m0", "modules.m0.icon", "modules.m0.audio")
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./menu[@id='m0']/display")

        self._assert_app_strings_available(self.app, 'en')

        icon_locale = id_strings.module_icon_locale(self.module)
        audio_locale = id_strings.module_audio_locale(self.module)
        self._test_correct_icon_translations(self.app, self.module, icon_locale)
        self._test_correct_audio_translations(self.app, self.module, audio_locale)

    def test_case_list_form_media(self):
        app = AppFactory.case_list_form_app_factory().app
        app.build_spec = self.min_spec

        no_media_xml = self.XML_without_media("case_list_form.m0", for_action_menu=True)
        self.assertXmlPartialEqual(
            no_media_xml,
            app.create_suite(),
            "./detail[@id='m0_case_short']/action/display"
        )

        app.get_module(0).case_list_form.set_icon('en', self.image_path)
        app.get_module(0).case_list_form.set_audio('en', self.audio_path)

        XML = self.makeXML("case_list_form.m0", "case_list_form.m0.icon", "case_list_form.m0.audio")
        self.assertXmlPartialEqual(XML, app.create_suite(), "./detail[@id='m0_case_short']/action/display")
        self._assert_app_strings_available(app, 'en')

        icon_locale = id_strings.case_list_form_icon_locale(app.get_module(0))
        audio_locale = id_strings.case_list_form_audio_locale(app.get_module(0))
        self._test_correct_icon_translations(app, app.get_module(0).case_list_form, icon_locale)
        self._test_correct_audio_translations(app, app.get_module(0).case_list_form, audio_locale)

    def test_case_list_menu_media(self):
        self.module.case_list.show = True

        no_media_xml = self.XML_without_media("case_lists.m0")
        self.assertXmlPartialEqual(no_media_xml, self.app.create_suite(), "./entry/command[@id='m0-case-list']/")

        self.module.case_list.set_icon('en', self.image_path)
        self.module.case_list.set_audio('en', self.audio_path)

        XML = self.makeXML(
            "case_lists.m0",
            "case_lists.m0.icon",
            "case_lists.m0.audio",
        )
        self.assertXmlPartialEqual(
            XML,
            self.app.create_suite(),
            "./entry/command[@id='m0-case-list']/"
        )
        self._assert_app_strings_available(self.app, 'en')

        icon_locale = id_strings.case_list_icon_locale(self.module)
        audio_locale = id_strings.case_list_audio_locale(self.module)
        self._test_correct_icon_translations(self.app, self.module.case_list, icon_locale)
        self._test_correct_audio_translations(self.app, self.module.case_list, audio_locale)

    def _assert_app_strings_available(self, app, lang):
        et = etree.XML(app.create_suite())
        locale_elems = et.findall(".//locale/[@id]")
        locale_strings = [elem.attrib['id'] for elem in locale_elems]

        app_strings = commcare_translations.loads(app.create_app_strings(lang))
        for string in locale_strings:
            if string not in app_strings:
                raise AssertionError("App strings did not contain %s" % string)
            if not app_strings.get(string, '').strip():
                raise AssertionError("App strings has blank entry for %s" % string)

    def _test_correct_icon_translations(self, app, menu, menu_locale_id):
        #  english should have right translation
        self._assert_valid_media_translation(app, 'en', menu_locale_id, self.image_path)
        #  default should have any random translation
        self._assert_valid_media_translation(app, 'default', menu_locale_id, self.image_path)
        #  hindi shouldn't have translation strings
        with self.assertRaises(KeyError):
            self._assert_valid_media_translation(app, 'hin', menu_locale_id, self.image_path)
        #  set media for hindi
        menu.set_icon('hin', self.hindi_image)
        #  hindi should have right translation
        self._assert_valid_media_translation(app, 'hin', menu_locale_id, self.hindi_image)

    def _test_correct_audio_translations(self, app, menu, menu_locale_id):
        #  english should have right translation
        self._assert_valid_media_translation(app, 'en', menu_locale_id, self.audio_path)
        #  default should have any random translation
        self._assert_valid_media_translation(app, 'default', menu_locale_id, self.audio_path)
        #  hindi shouldn't have translation strings
        with self.assertRaises(KeyError):
            self._assert_valid_media_translation(app, 'hin', menu_locale_id, self.audio_path)
        #  set media for hindi
        menu.set_audio('hin', self.hindi_audio)
        #  hindi should have right translation
        self._assert_valid_media_translation(app, 'hin', menu_locale_id, self.hindi_audio)

    def _assert_valid_media_translation(self, app, lang, media_locale_id, media_path):
        # assert that <lang>/app_strings.txt contains media_locale_id=media_path
        app_strings = commcare_translations.loads(app.create_app_strings(lang))
        self.assertEqual(app_strings[media_locale_id], media_path)
