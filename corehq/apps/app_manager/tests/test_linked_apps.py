import json
import os
import uuid

from couchdbkit.exceptions import ResourceNotFound
from django.test.testcases import TestCase
from mock import patch

from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models import (
    Application,
    ReportModule, ReportAppConfig, Module, RemoteAppDetails)
from corehq.apps.app_manager.remote_link_accessors import _convert_app_from_remote_linking_source, \
    _get_missing_multimedia, _fetch_remote_media
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.views.remote_linked_apps import _convert_app_for_remote_linking
from corehq.apps.app_manager.views.utils import overwrite_app
from corehq.apps.hqmedia.models import CommCareImage, CommCareMultimedia


def fetch_missing_multimedia(linked_app):
    pass


class TestLinkedApps(TestCase, TestXmlMixin):
    file_path = ('data',)

    @classmethod
    def setUpClass(cls):
        super(TestLinkedApps, cls).setUpClass()
        cls.master_app = Application.new_app('domain', "Master Application")
        cls.linked_app = Application.new_app('domain-2', "Linked Application")
        module = cls.master_app.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [
            ReportAppConfig(report_id='id', header={'en': 'CommBugz'}),
        ]
        cls.linked_app.save()

        image_data = cls._get_image_data('commcare-hq-logo.png')
        cls.image = CommCareImage.get_by_data(image_data)
        cls.image.attach_data(image_data, original_filename='logo.png')
        cls.image.add_domain(cls.master_app.domain)

    @classmethod
    def tearDownClass(cls):
        cls.linked_app.delete()
        cls.image.delete()
        super(TestLinkedApps, cls).tearDownClass()

    @staticmethod
    def _get_image_data(filename):
        image_path = os.path.join('corehq', 'apps', 'hqwebapp', 'static', 'hqwebapp', 'images', filename)
        with open(image_path, 'r') as f:
            return f.read()

    def test_missing_ucrs(self):
        with self.assertRaises(AppEditingError):
            overwrite_app(self.linked_app, self.master_app, {})

    def test_report_mapping(self):
        report_map = {'id': 'mapped_id'}
        overwrite_app(self.linked_app, self.master_app, report_map)
        linked_app = Application.get(self.linked_app._id)
        self.assertEqual(linked_app.modules[0].report_configs[0].report_id, 'mapped_id')

    def test_remote_app(self):
        module = self.master_app.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form'))

        linked_app = _mock_pull_remote_master(self.master_app, self.linked_app, {'id': 'mapped_id'})
        self.assertEqual(self.master_app.get_attachments(), linked_app.get_attachments())

    def test_get_missing_media_list(self):
        image_path = 'jr://file/commcare/case_list_image.jpg'
        self.master_app.get_module(0).set_icon('en', image_path)

        self.master_app.create_mapping(self.image, image_path, save=False)

        with patch('corehq.apps.hqmedia.models.CommCareMultimedia.get', side_effect=ResourceNotFound):
            missing_media = _get_missing_multimedia(self.master_app)

        self.assertEqual(missing_media, self.master_app.multimedia_map.values())

    def test_add_domain_to_media(self):
        self.image.valid_domains.remove(self.master_app.domain)
        self.image.save()

        image = CommCareImage.get(self.image._id)
        self.assertNotIn(self.master_app.domain, image.valid_domains)

        image_path = 'jr://file/commcare/case_list_image.jpg'
        self.master_app.get_module(0).set_icon('en', image_path)
        self.master_app.create_mapping(self.image, image_path, save=False)

        missing_media = _get_missing_multimedia(self.master_app)
        self.assertEqual(missing_media, [])

        image = CommCareImage.get(self.image._id)
        self.assertIn(self.master_app.domain, image.valid_domains)

    def test_fetch_missing_media(self):
        image_path = 'jr://file/commcare/case_list_image.jpg'
        self.master_app.get_module(0).set_icon('en', image_path)
        self.master_app.create_mapping(self.image, image_path, save=False)

        remote_app_details = RemoteAppDetails(
            'http://localhost:8000', 'test_domain', 'user', 'key', self.master_app._id
        )
        data = 'this is a test'
        media_details = self.master_app.multimedia_map.values()[0]
        media_details['multimedia_id'] = uuid.uuid4().hex
        media_details['media_type'] = 'CommCareMultimedia'
        with patch('corehq.apps.app_manager.remote_link_accessors._fetch_remote_media_content') as mock:
            mock.return_value = data
            _fetch_remote_media('domain', [media_details], remote_app_details)

        media = CommCareMultimedia.get(media_details['multimedia_id'])
        self.addCleanup(media.delete)
        content = media.fetch_attachment(media.blobs.keys()[0])
        self.assertEqual(data, content)


def _mock_pull_remote_master(master_app, linked_app, report_map=None):
    master_source = _convert_app_for_remote_linking(master_app)
    master_app = _convert_app_from_remote_linking_source(master_source)
    overwrite_app(linked_app, master_app, report_map or {})
    return Application.get(linked_app._id)
