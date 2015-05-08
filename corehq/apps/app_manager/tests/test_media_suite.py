from django.test import TestCase
from django.test.utils import override_settings
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.builds.models import BuildSpec
from corehq.apps.hqmedia.models import CommCareImage


class MediaSuiteTest(TestCase, TestFileMixin):
    file_path = ('data', 'suite')

    @override_settings(BASE_ADDRESS='192.cc.hq.1')
    def test_case_list_media(self):
        app = Application.wrap(self.get_json('app'))
        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id

        image_path = 'jr://file/commcare/case_list_image.jpg'
        audo_path = 'jr://file/commcare/case_list_audo.mp3'
        app.get_module(0).case_list_form.set_icon('en', image_path, default_lang=app.default_language)
        app.get_module(0).case_list_form.set_audio('en', audo_path, default_lang=app.default_language)

        app.create_mapping(CommCareImage(_id='123'), image_path, save=False)
        app.create_mapping(CommCareImage(_id='456'), audo_path, save=False)

        self.assertXmlEqual(self.get_xml('media_suite'), app.create_media_suite())


class LocalizedMediaSuiteTest(TestCase, TestFileMixin):

    def setUp(self):
        self.image_path = 'jr://file/commcare/case_list_image.jpg'
        self.audio_path = 'jr://file/commcare/case_list_audo.mp3'
        self.app = Application.new_app('domain', "my app", application_version=APP_V2)
        self.app.build_spec = BuildSpec.from_string('2.21/latest')

    def test_form_suite(self):

        self.app.add_module(Module.new_module("Module 1", None))
        form = self.app.new_form(0, "Form 1", None)

        form.set_icon('en', self.image_path)
        form.set_audio('en', self.audio_path)

        XML = """
        <partial>
            <entry>
              <command id="m0-f0">
                <display>
                  <text>
                    <locale id="forms.m0f0"/>
                  </text>
                  <text form="image">
                    <locale id="forms.m0f0.icon"/>
                  </text>
                  <text form="audio">
                    <locale id="forms.m0f0.audio"/>
                  </text>
                </display>
              </command>
            </entry>
        </partial>
        """
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./entry")

    def test_module_suite(self):

        module = self.app.add_module(Module.new_module("Module 1", None))
        self.app.new_form(0, "Form 1", None)

        module.set_icon('en', self.image_path)
        module.set_audio('en', self.audio_path)

        XML = """
        <partial>
            <display>
                <text>
                    <locale id="modules.m0"/>
                </text>
                <text form="image">
                    <locale id="modules.m0.icon"/>
                </text>
                <text form="audio">
                    <locale id="modules.m0.audio"/>
                </text>
            </display>
        </partial>
        """

        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./menu[@id='m0']/display")
