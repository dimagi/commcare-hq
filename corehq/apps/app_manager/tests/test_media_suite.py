from copy import deepcopy
from django.test import SimpleTestCase
from django.test.utils import override_settings
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, ReportModule, ReportAppConfig
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio


class MediaSuiteTest(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')

    @override_settings(BASE_ADDRESS='192.cc.hq.1')
    def test_case_list_media(self):
        app = Application.wrap(self.get_json('app'))
        app.get_module(0).case_list_form.form_id = app.get_module(0).get_form(0).unique_id

        image_path = 'jr://file/commcare/case_list_image.jpg'
        audo_path = 'jr://file/commcare/case_list_audo.mp3'
        app.get_module(0).case_list_form.media_image = image_path
        app.get_module(0).case_list_form.media_audio = audo_path

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
        app.get_module(0).case_list_form.media_image = image_path

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
