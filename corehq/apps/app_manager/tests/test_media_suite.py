from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings
from lxml import etree

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.builds.models import BuildSpec
from corehq.apps.hqmedia.models import CommCareImage

import commcare_translations


class MediaSuiteTest(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')

    @override_settings(BASE_ADDRESS='192.cc.hq.1')
    def test_case_list_media(self):
        app = Application.wrap(self.get_json('app'))
        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id

        image_path = 'jr://file/commcare/case_list_image.jpg'
        audo_path = 'jr://file/commcare/case_list_audo.mp3'
        app.get_module(0).case_list_form.set_icon('en', image_path)
        app.get_module(0).case_list_form.set_audio('en', audo_path)

        app.create_mapping(CommCareImage(_id='123'), image_path, save=False)
        app.create_mapping(CommCareImage(_id='456'), audo_path, save=False)

        self.assertXmlEqual(self.get_xml('media_suite'), app.create_media_suite())


class LocalizedMediaSuiteTest(TestCase, TestFileMixin):
    """
        For CC >= 2.21
    """
    file_path = ('data', 'suite')

    def setUp(self):
        self.image_path = 'jr://file/commcare/case_list_image.jpg'
        self.audio_path = 'jr://file/commcare/case_list_audo.mp3'
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

    def test_no_media(self):
        XML = """
        <partial>
            <text>
                <locale id="forms.m0f0"/>
            </text>
        </partial>
        """
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./entry/command[@id='m0-f0']/")

    def _test_form_suite(self, lang):
        self.form.set_icon(lang, self.image_path)
        self.form.set_audio(lang, self.audio_path)

        XML = self.makeXML("forms.m0f0", "forms.m0f0.icon", "forms.m0f0.audio")
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./entry/command[@id='m0-f0']/display")

    def test_form_suite_english(self):
        self._test_form_suite('en')

    def test_form_suite_hindi(self):
        self._test_form_suite('hin')

    def test_module_suite(self):
        self.module.set_icon('en', self.image_path)
        self.module.set_audio('en', self.audio_path)

        XML = self.makeXML("modules.m0", "modules.m0.icon", "modules.m0.audio")
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./menu[@id='m0']/display")

    def test_case_list_form_media(self):
        app = Application.wrap(self.get_json('app'))
        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id

        app.get_module(0).case_list_form.set_icon('en', self.image_path)
        app.get_module(0).case_list_form.set_audio('en', self.audio_path)
        app.build_spec = self.min_spec

        XML = self.makeXML("case_list_form.m0", "case_list_form.m0.icon", "case_list_form.m0.audio")
        self.assertXmlPartialEqual(XML, app.create_suite(), "./detail[@id='m0_case_short']/action/display")

    def test_media_app_strings(self):
        self.form.set_icon('en', self.image_path)
        self.form.set_audio('en', self.audio_path)

        et = etree.XML(self.app.create_suite())
        locale_elems = et.findall(".//locale/[@id]")
        locale_strings = [elem.attrib['id'] for elem in locale_elems]

        app_strings = commcare_translations.loads(self.app.create_app_strings('en'))
        for string in locale_strings:
            if string not in app_strings:
                raise AssertionError("App strings did not contain %s" % string)
            if not app_strings.get(string, '').strip():
                raise AssertionError("App strings has blank entry for %s" % string)

    def test_localized_app_strings(self):
        self.form.set_icon('en', self.image_path)

        en_app_strings = commcare_translations.loads(self.app.create_app_strings('en'))
        hin_app_strings = commcare_translations.loads(self.app.create_app_strings('hin'))

        form_icon_locale = id_strings.form_icon_locale(self.form)
        self.assertEqual(en_app_strings[form_icon_locale], self.image_path)
        self.assertEqual(hin_app_strings[form_icon_locale], self.image_path)
