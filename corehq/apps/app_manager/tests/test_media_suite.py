# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from copy import deepcopy
from django.test import SimpleTestCase
from django.test.utils import override_settings
from lxml import etree
from mock import patch

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.models import Application, Module, GraphConfiguration, \
    GraphSeries, ReportModule, ReportAppConfig, CustomIcon
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

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_all_media_paths_with_inline_video(self, mock):
        inline_video_path = 'jr://file/commcare/video-inline/data/inline_video.mp4'
        app = Application.wrap(self.get_json('app_video_inline'))

        self.assertTrue(app.get_module(0).uses_media())
        self.assertEqual(app.all_media_paths, set([inline_video_path]))

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_all_media_paths_with_expanded_audio(self, mock):
        inline_video_path = 'jr://file/commcare/expanded-audio/data/expanded_audio.mp3'
        app = Application.wrap(self.get_json('app_expanded_audio'))

        self.assertTrue(app.get_module(0).uses_media())
        self.assertEqual(app.all_media_paths, set([inline_video_path]))

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
        Report Modules support media
        """
        from corehq.apps.userreports.tests.utils import get_sample_report_config

        app = Application.new_app('domain', "Untitled Application")

        report_module = app.add_module(ReportModule.new_module('Reports', None))
        report_module.unique_id = 'report_module'
        report = get_sample_report_config()
        report._id = 'd3ff18cd83adf4550b35db8d391f6008'

        report_app_config = ReportAppConfig(report_id=report._id,
                                            header={'en': 'CommBugz'},
                                            complete_graph_configs={
                                                chart.chart_id: GraphConfiguration(
                                                    series=[GraphSeries() for c in chart.y_axis_columns],
                                                )
                                                for chart in report.charts
                                            })
        report_app_config._report = report
        report_module.report_configs = [report_app_config]
        report_module._loaded = True

        image_path = 'jr://file/commcare/case_list_image.jpg'
        audio_path = 'jr://file/commcare/case_list_audo.mp3'
        app.get_module(0).media_image.update({'en': image_path})
        app.get_module(0).media_audio.update({'en': audio_path})

        self.assertTrue(app.get_module(0).uses_media())
        self.assertEqual(len(app.all_media), 2)


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
        self.app = Application.new_app('domain', "my app")
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

    def test_custom_icons_in_modules(self):
        self._test_custom_icon_in_suite(
            self.module, "modules.m0",
            id_strings.module_custom_icon_locale, "./menu[@id='m0']/display")

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

    def test_custom_icons_in_forms(self):
        self._test_custom_icon_in_suite(
            self.form, "forms.m0f0",
            id_strings.form_custom_icon_locale, "./entry/command[@id='m0-f0']/")

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

    def _test_custom_icon_in_suite(self, form_or_module, locale_id, custom_icon_locale_method, xml_node):
        """
        :param form_or_module: form or module for which to test
        :param locale_id: text locale id in display block for form or module
        :param custom_icon_locale_method: method to find locale id in app strings for custom icon
        :param xml_node: where to find the xml partial for comparison
        """
        custom_icon = CustomIcon(form="badge", text={'en': 'IconText', 'hin': 'चित्र'})
        form_or_module.custom_icons = [custom_icon]

        custom_icon_block_template = """
            <partial>
                <display>
                    <text>
                        <locale id="{locale_id}"/>
                    </text>
                    <text form="badge">
                        {locale_or_xpath}
                    </text>
                </display>
            </partial>
        """
        custom_icon_locale = custom_icon_locale_method(form_or_module, custom_icon.form)
        text_locale_partial = '<locale id="{custom_icon_locale}"/>'.format(custom_icon_locale=custom_icon_locale)

        # check for text locale
        custom_icon_block = custom_icon_block_template.format(locale_id=locale_id,
                                                              locale_or_xpath=text_locale_partial)
        self.assertXmlPartialEqual(custom_icon_block, self.app.create_suite(), xml_node)
        self._assert_app_strings_available(self.app, 'en')

        # check for translation for text locale
        self._assert_valid_media_translation(self.app, 'hin', custom_icon_locale, custom_icon.text['hin'])

        # check for default in case of missing translation
        self._assert_valid_media_translation(self.app, 'secret', custom_icon_locale, custom_icon.text['en'])

        # check for xpath being set for custom icon
        custom_icon.xpath = "if(1=1, 'a', 'b')"
        custom_icon.text = {}
        form_or_module.custom_icons = [custom_icon]
        custom_icon_block = custom_icon_block_template.format(
            locale_id=locale_id,
            locale_or_xpath='<xpath function="{xpath}"/>'.format(xpath=custom_icon.xpath)
        )
        self.assertXmlPartialEqual(custom_icon_block, self.app.create_suite(), xml_node)
