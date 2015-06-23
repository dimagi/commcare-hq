from copy import deepcopy
from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings
from lxml import etree

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module, ReportModule, ReportAppConfig
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.builds.models import BuildSpec
from corehq.apps.hqmedia.models import CommCareImage

import commcare_translations


class MediaSuiteTest(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')

    def test_all_media_paths(self):
        image_path = 'jr://file/commcare/image{}.jpg'
        app = Application.wrap(self.get_json('app'))

        app.get_module(0).case_list.show = True
        app.get_module(0).case_list.set_icon('en', image_path.format('4'))

        app.get_module(0).set_icon('en', image_path.format('1'))

        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id
        app.get_module(0).case_list_form.set_icon('en', image_path.format('2'))

        app.get_module(0).get_form(0).set_icon('en', image_path.format('3'))

        should_contain_images = [image_path.format(num) for num in [1, 2, 3, 4]]
        self.assertEqual(app.all_media_paths, set(should_contain_images))

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

    def test_all_media_basic_module(self):
        app = Application.wrap(self.get_json('app'))
        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id

        image_path = 'jr://file/commcare/case_list_image.jpg'
        audo_path = 'jr://file/commcare/case_list_audo.mp3'
        app.get_module(0).case_list_form.media_image = image_path
        app.get_module(0).case_list_form.media_audio = audo_path

        app.create_mapping(CommCareImage(_id='123'), image_path, save=False)
        app.create_mapping(CommCareImage(_id='456'), audo_path, save=False)

        self.assertTrue(app.get_module(0).uses_media())
        self.assertEqual(len(app.all_media), 2)

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
        audo_path = 'jr://file/commcare/case_list_audo.mp3'
        app.get_module(0).case_list_form.media_image = image_path
        app.get_module(0).case_list_form.media_audio = audo_path

        self.assertFalse(app.get_module(0).uses_media())
        self.assertEqual(len(app.all_media), 0)

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
