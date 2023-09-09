import uuid
from collections import OrderedDict
from copy import deepcopy

from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings

from lxml import etree
from unittest.mock import patch

import commcare_translations
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.generator import MediaSuiteGenerator
from corehq.apps.app_manager.models import (
    Application,
    BuildProfile,
    CustomIcon,
    GraphConfiguration,
    GraphSeries,
    Module,
    ReportAppConfig,
    ReportModule,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin, parse_normalize, patch_get_xform_resource_overrides
from corehq.apps.builds.models import BuildSpec
from corehq.apps.hqmedia.models import CommCareAudio, CommCareImage, CommCareVideo
from corehq.util.test_utils import softer_assert


class MediaSuiteTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def _assertMediaSuiteResourcesEqual(self, expectedXml, actualXml):
        parsedExpected = parse_normalize(expectedXml, to_string=False)
        expectedResources = {node.text for node in parsedExpected.findall("media/resource/location")}
        parsedActual = parse_normalize(actualXml, to_string=False)
        actualResources = {node.text for node in parsedActual.findall("media/resource/location")}
        self.assertSetEqual(expectedResources, actualResources)

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_all_media_paths(self, mock):
        image_path = 'jr://file/commcare/image{}.jpg'
        audio_path = 'jr://file/commcare/audio{}.mp3'
        app = Application.wrap(self.get_json('app'))

        for num in ['1', '2', '3', '4']:
            app.create_mapping(CommCareImage(_id=num), image_path.format(num), save=False)
            app.create_mapping(CommCareAudio(_id=num), audio_path.format(num), save=False)
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
        self.assertEqual(app.all_media_paths(), set(should_contain_media))
        self.assertEqual(set(app.multimedia_map.keys()), set(should_contain_media))

        # test multimedia removed
        app.get_module(0).case_list.set_icon('en', '')
        app.get_module(0).case_list.set_audio('en', '')
        app.get_module(0).set_icon('en', '')
        app.get_module(0).set_audio('en', '')
        app.get_module(0).case_list_form.set_icon('en', '')
        app.get_module(0).case_list_form.set_audio('en', '')
        app.get_module(0).get_form(0).set_icon('en', '')
        app.get_module(0).get_form(0).set_audio('en', '')
        self.assertFalse(list(app.multimedia_map.keys()))

    def test_media_suite_generator(self):
        app = Application.wrap(self.get_json('app_video_inline'))
        image_path = 'jr://file/commcare/image1.jpg'
        audio_path = 'jr://file/commcare/audio1.mp3'
        video_path = 'jr://file/commcare/video-inline/data/inline_video.mp4'
        app.create_mapping(CommCareImage(_id='123'), image_path, save=False)
        app.create_mapping(CommCareAudio(_id='456'), audio_path, save=False)
        app.create_mapping(CommCareVideo(_id='789'), video_path, save=False)
        app.get_module(0).case_list_form.set_icon('en', image_path)
        app.get_module(0).case_list_form.set_audio('en', audio_path)
        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id

        app.profile["properties"] = {
            'lazy-load-video-files': 'true'
        }
        self.assertXmlEqual(self.get_xml('media-suite-lazy-true'), MediaSuiteGenerator(app).generate_suite())

        app.profile["properties"] = {
            'lazy-load-video-files': 'false'
        }
        self.assertXmlEqual(self.get_xml('media-suite-lazy-false'), MediaSuiteGenerator(app).generate_suite())

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_all_media_paths_with_inline_video(self, mock):
        inline_video_path = 'jr://file/commcare/video-inline/data/inline_video.mp4'
        app = Application.wrap(self.get_json('app_video_inline'))

        self.assertTrue(app.get_module(0).uses_media())
        self.assertEqual(app.all_media_paths(), set([inline_video_path]))

    @override_settings(BASE_ADDRESS='192.cc.hq.1')
    @patch('corehq.apps.app_manager.models.ApplicationBase.get_latest_build', lambda _: None)
    def test_case_list_media(self):
        app = Application.wrap(self.get_json('app'))
        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id

        image_path = 'jr://file/commcare/case_list_image.jpg'
        audo_path = 'jr://file/commcare/case_list_audo.mp3'
        app.get_module(0).case_list_form.set_icon('en', image_path)
        app.get_module(0).case_list_form.set_audio('en', audo_path)

        app.create_mapping(CommCareImage(_id='123'), image_path, save=False)
        app.create_mapping(CommCareAudio(_id='456'), audo_path, save=False)

        app.set_media_versions()

        self._assertMediaSuiteResourcesEqual(self.get_xml('case_list_media_suite'), app.create_media_suite())

    @patch('corehq.apps.hqmedia.models.domain_has_privilege', return_value=True)
    @patch('corehq.apps.app_manager.models.ApplicationBase.get_latest_build', lambda _: None)
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    @override_settings(BASE_ADDRESS='192.cc.hq.1')
    def test_form_media_with_app_profile(self, *args):
        # Test that media for languages not in the profile are removed from the media suite

        app = Application.wrap(self.get_json('app'))
        app.build_profiles = OrderedDict({
            'en': BuildProfile(langs=['en'], name='en-profile'),
            'hin': BuildProfile(langs=['hin'], name='hin-profile'),
            'all': BuildProfile(langs=['en', 'hin'], name='all-profile'),
        })
        app.langs = ['en', 'hin']

        image_path = 'jr://file/commcare/module0_en.png'
        audio_path = 'jr://file/commcare/module0_{}.mp3'
        app.get_module(0).set_icon('en', image_path)
        app.get_module(0).set_audio('en', audio_path.format('en'))
        app.get_module(0).set_audio('hin', audio_path.format('hin'))

        app.create_mapping(CommCareImage(_id='123'), image_path, save=False)
        app.create_mapping(CommCareAudio(_id='456'), audio_path.format('en'), save=False)
        app.create_mapping(CommCareAudio(_id='789'), audio_path.format('hin'), save=False)

        form_xml = self.get_xml('form_with_media_refs').decode('utf-8')
        form = app.get_module(0).new_form('form_with_media', 'en', attachment=form_xml)
        xform = form.wrapped_xform()
        for i, path in enumerate(reversed(sorted(xform.media_references(form="audio")))):
            app.create_mapping(CommCareAudio(_id='form_audio_{}'.format(i)), path, save=False)
        for i, path in enumerate(sorted(xform.media_references(form="image"))):
            app.create_mapping(CommCareImage(_id='form_image_{}'.format(i)), path, save=False)

        app.set_media_versions()
        app.remove_unused_mappings()

        # includes all media
        self._assertMediaSuiteResourcesEqual(self.get_xml('form_media_suite'), app.create_media_suite())

        # generate all suites at once to mimic create_build_files_for_all_app_profiles
        suites = {id: app.create_media_suite(build_profile_id=id) for id in app.build_profiles.keys()}

        # include all app media and only language-specific form media
        self._assertMediaSuiteResourcesEqual(self.get_xml('form_media_suite_en'), suites['en'])
        self._assertMediaSuiteResourcesEqual(self.get_xml('form_media_suite_hin'), suites['hin'])
        self._assertMediaSuiteResourcesEqual(self.get_xml('form_media_suite_all'), suites['all'])

    @patch('corehq.apps.app_manager.models.ApplicationBase._get_version_comparison_build')
    def test_update_image_id(self, get_latest_build):
        """
        When an image is updated, change only version number, not resource id
        """
        app = Application.wrap(self.get_json('app'))
        image_path = 'jr://file/commcare/case_list_image.jpg'
        app.get_module(0).case_list_form.set_icon('en', image_path)

        app.version = 1
        app.create_mapping(CommCareImage(_id='123'), image_path, save=False)
        get_latest_build.return_value = None
        app.set_media_versions()
        old_app = deepcopy(app)

        app.version = 2
        app.create_mapping(CommCareImage(_id='456'), image_path, save=False)
        get_latest_build.return_value = old_app
        app.set_media_versions()

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
        self.assertEqual(len(app.all_media()), 2)


class TestRemoveMedia(TestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    @classmethod
    def setUpClass(cls):
        super(TestRemoveMedia, cls).setUpClass()
        cls.domain = uuid.uuid4().hex

    @softer_assert()
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_unused_media_removed(self, mock):
        image_path = 'jr://file/commcare/image{}_{}.jpg'
        audio_path = 'jr://file/commcare/audio{}_{}.mp3'
        app = Application.wrap(self.get_json('app'))
        app.domain = self.domain
        app.save()

        for lang in ['en', 'hin']:
            for num in ['1', '2', '3', '4']:
                app.create_mapping(CommCareImage(_id=num), image_path.format(num, lang), save=False)
                app.create_mapping(CommCareAudio(_id=num), audio_path.format(num, lang), save=False)
        app.get_module(0).case_list.show = True
        app.get_module(0).case_list.set_icon('en', image_path.format('4', 'en'))
        app.get_module(0).case_list.set_audio('en', audio_path.format('4', 'en'))

        app.get_module(0).set_icon('en', image_path.format('1', 'en'))
        app.get_module(0).set_audio('en', audio_path.format('1', 'en'))

        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id
        app.get_module(0).case_list_form.set_icon('en', image_path.format('2', 'en'))
        app.get_module(0).case_list_form.set_audio('en', audio_path.format('2', 'en'))

        app.get_module(0).get_form(0).set_icon('en', image_path.format('3', 'en'))
        app.get_module(0).get_form(0).set_audio('en', audio_path.format('3', 'en'))

        app.save()

        should_contain_media = [image_path.format(num, 'en') for num in [1, 2, 3, 4]] + \
                               [audio_path.format(num, 'en') for num in [1, 2, 3, 4]]
        media_for_removal = [image_path.format(num, 'hin') for num in [1, 2, 3, 4]] + \
                            [audio_path.format(num, 'hin') for num in [1, 2, 3, 4]]
        self.assertTrue(app.get_module(0).uses_media())
        self.assertEqual(app.all_media_paths(), set(should_contain_media))
        self.assertEqual(set(app.multimedia_map.keys()), set(should_contain_media + media_for_removal))
        app.remove_unused_mappings()
        self.assertEqual(set(app.multimedia_map.keys()), set(should_contain_media))

        # test multimedia removed
        app.get_module(0).case_list.set_icon('en', '')
        app.get_module(0).case_list.set_audio('en', '')
        app.get_module(0).set_icon('en', '')
        app.get_module(0).set_audio('en', '')
        app.get_module(0).case_list_form.set_icon('en', '')
        app.get_module(0).case_list_form.set_audio('en', '')
        app.get_module(0).get_form(0).set_icon('en', '')
        app.get_module(0).get_form(0).set_audio('en', '')
        self.assertFalse(list(app.multimedia_map.keys()))


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
        self.min_spec = BuildSpec.from_string('2.54.0/latest')
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

    @patch_get_xform_resource_overrides()
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

    @patch_get_xform_resource_overrides()
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

    @patch_get_xform_resource_overrides()
    def test_custom_icons_in_modules(self):
        self._test_custom_icon_in_suite(
            self.module, "modules.m0",
            id_strings.module_custom_icon_locale, "./menu[@id='m0']", "display")

    @patch_get_xform_resource_overrides()
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

    @patch_get_xform_resource_overrides()
    def test_custom_icons_in_forms(self):
        self._test_custom_icon_in_suite(
            self.form, "forms.m0f0",
            id_strings.form_custom_icon_locale, "./entry", "command[@id='m0-f0']/")

    @patch_get_xform_resource_overrides()
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

    def test_use_default_media(self):
        self.app.langs = ['en', 'hin']

        self.module.use_default_image_for_all = True
        self.module.use_default_audio_for_all = True

        self.module.set_icon('en', self.image_path)
        self.module.set_audio('en', self.audio_path)
        self.module.set_icon('hin', 'jr://file/commcare/case_list_image_hin.jpg')
        self.module.set_audio('hin', 'jr://file/commcare/case_list_audio_hin.mp3')

        en_app_strings = commcare_translations.loads(self.app.create_app_strings('en'))
        hin_app_strings = commcare_translations.loads(self.app.create_app_strings('hin'))
        self.assertEqual(en_app_strings['modules.m0.icon'], hin_app_strings['modules.m0.icon'])
        self.assertEqual(en_app_strings['modules.m0.audio'], hin_app_strings['modules.m0.audio'])

    @patch_get_xform_resource_overrides()
    def test_use_default_media_ignore_lang(self):
        # When use_default_media is true and there's media in a non-default language but not the default language
        self.app.langs = ['en', 'hin']

        self.form.use_default_image_for_all = True
        self.form.use_default_audio_for_all = True

        self.form.set_icon('en', '')
        self.form.set_audio('en', '')
        self.form.set_icon('hin', 'jr://file/commcare/case_list_image_hin.jpg')
        self.form.set_audio('hin', 'jr://file/commcare/case_list_audio_hin.mp3')

        en_app_strings = commcare_translations.loads(self.app.create_app_strings('en'))
        hin_app_strings = commcare_translations.loads(self.app.create_app_strings('hin'))

        self.assertFalse('forms.m0f0.icon' in en_app_strings)
        self.assertFalse('forms.m0f0.icon' in hin_app_strings)
        self.assertFalse('forms.m0f0.audio' in en_app_strings)
        self.assertFalse('forms.m0f0.audio' in hin_app_strings)

        self.assertXmlPartialEqual(
            self.XML_without_media("forms.m0f0"),
            self.app.create_suite(),
            "./entry/command[@id='m0-f0']/"
        )

    @patch_get_xform_resource_overrides()
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_suite_media_with_app_profile(self, *args):
        # Test that suite includes only media relevant to the profile

        app = Application.new_app('domain', "my app")
        app.add_module(Module.new_module("Module 1", None))
        app.new_form(0, "Form 1", None)
        app.build_spec = BuildSpec.from_string('2.21.0/latest')
        app.build_profiles = OrderedDict({
            'en': BuildProfile(langs=['en'], name='en-profile'),
            'hin': BuildProfile(langs=['hin'], name='hin-profile'),
            'all': BuildProfile(langs=['en', 'hin'], name='all-profile'),
        })
        app.langs = ['en', 'hin']

        image_path = 'jr://file/commcare/module0_en.png'
        audio_path = 'jr://file/commcare/module0_en.mp3'
        app.get_module(0).set_icon('en', image_path)
        app.get_module(0).set_audio('en', audio_path)

        # Generate suites and default app strings for each profile
        suites = {}
        locale_ids = {}
        for build_profile_id in app.build_profiles.keys():
            suites[build_profile_id] = app.create_suite(build_profile_id=build_profile_id)
            default_app_strings = app.create_app_strings('default', build_profile_id)
            locale_ids[build_profile_id] = {line.split('=')[0] for line in default_app_strings.splitlines()}

        # Suite should have only the relevant images
        media_xml = self.makeXML("modules.m0", "modules.m0.icon", "modules.m0.audio")
        self.assertXmlPartialEqual(media_xml, suites['all'], "././menu[@id='m0']/display")

        no_media_xml = self.XML_without_media("modules.m0")
        self.assertXmlPartialEqual(media_xml, suites['en'], "././menu[@id='m0']/display")

        no_media_xml = self.XML_without_media("modules.m0")
        self.assertXmlPartialEqual(no_media_xml, suites['hin'], "././menu[@id='m0']/text")

        # Default app strings should have only the relevant locales
        self.assertIn('modules.m0', locale_ids['all'])
        self.assertIn('modules.m0.icon', locale_ids['all'])
        self.assertIn('modules.m0.audio', locale_ids['all'])

        self.assertIn('modules.m0', locale_ids['en'])
        self.assertIn('modules.m0.icon', locale_ids['en'])
        self.assertIn('modules.m0.audio', locale_ids['en'])

        self.assertIn('modules.m0', locale_ids['hin'])
        self.assertNotIn('modules.m0.icon', locale_ids['hin'])
        self.assertNotIn('modules.m0.audio', locale_ids['hin'])

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

    def _test_custom_icon_in_suite(self, form_or_module, locale_id, custom_icon_locale_method, xpath_base,
                                   xpath_display_node):
        """
        :param form_or_module: form or module for which to test
        :param locale_id: text locale id in display block for form or module
        :param custom_icon_locale_method: method to find locale id in app strings for custom icon
        :param xml_node: where to find the xml partial for comparison
        """

        xpath_full = f"{xpath_base}/{xpath_display_node}"
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
        self.assertXmlPartialEqual(custom_icon_block, self.app.create_suite(), xpath_full)
        self._assert_app_strings_available(self.app, 'en')

        # check for translation for text locale
        self._assert_valid_media_translation(self.app, 'hin', custom_icon_locale, custom_icon.text['hin'])

        # check for default in case of missing translation
        self._assert_valid_media_translation(self.app, 'secret', custom_icon_locale, custom_icon.text['en'])

        # check for xpath being set for custom icon
        custom_icon.xpath = "if(1=1, 'a', instance('casedb')/casedb/case[@case_id='b']/case_name)"
        custom_icon.text = {}
        form_or_module.custom_icons = [custom_icon]
        custom_icon_block = custom_icon_block_template.format(
            locale_id=locale_id,
            locale_or_xpath='<xpath function="{xpath}"/>'.format(xpath=custom_icon.xpath)
        )
        suite = self.app.create_suite()
        self.assertXmlPartialEqual(custom_icon_block, suite, xpath_full)
        expected_instances = """
        <partial>
            <instance id="casedb" src="jr://instance/casedb"/>
        </partial>
        """
        self.assertXmlPartialEqual(expected_instances, suite, f"{xpath_base}/instance")
