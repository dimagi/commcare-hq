from __future__ import absolute_import
from __future__ import unicode_literals
import os
import uuid

from couchdbkit.exceptions import ResourceNotFound
from django.test.testcases import TestCase
from mock import patch

from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models import (
    Application,
    ReportModule, ReportAppConfig, Module, LinkedApplication)
from corehq.apps.linked_domain.dbaccessors import get_domain_master_link
from corehq.apps.linked_domain.exceptions import ActionNotPermitted
from corehq.apps.linked_domain.models import DomainLink, RemoteLinkDetails
from corehq.apps.linked_domain.remote_accessors import _convert_app_from_remote_linking_source, \
    _get_missing_multimedia, _fetch_remote_media
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.views.utils import overwrite_app, _get_form_id_map
from corehq.apps.hqmedia.models import CommCareImage, CommCareMultimedia
from corehq.apps.linked_domain.util import convert_app_for_remote_linking


class BaseLinkedAppsTest(TestCase, TestXmlMixin):
    file_path = ('data',)

    @classmethod
    def setUpClass(cls):
        super(BaseLinkedAppsTest, cls).setUpClass()
        cls.master_app_with_report_modules = Application.new_app('domain', "Master Application")
        module = cls.master_app_with_report_modules.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [
            ReportAppConfig(report_id='id', header={'en': 'CommBugz'}),
        ]

        cls.plain_master_app = Application.new_app('domain', "Master Application")
        cls.plain_master_app.linked_whitelist = ['domain-2']
        cls.plain_master_app.save()

        cls.linked_app = LinkedApplication.new_app('domain-2', "Linked Application")
        cls.linked_app.save()

        cls.domain_link = DomainLink.link_domains('domain-2', 'domain')

    @classmethod
    def tearDownClass(cls):
        cls.linked_app.delete()
        cls.plain_master_app.delete()
        cls.domain_link.delete()
        super(BaseLinkedAppsTest, cls).tearDownClass()

    def setUp(self):
        # re-fetch app
        self.linked_app = LinkedApplication.get(self.linked_app._id)


class TestLinkedApps(BaseLinkedAppsTest):
    def test_missing_ucrs(self):
        with self.assertRaises(AppEditingError):
            overwrite_app(self.linked_app, self.master_app_with_report_modules, {})

    def test_report_mapping(self):
        report_map = {'id': 'mapped_id'}
        overwrite_app(self.linked_app, self.master_app_with_report_modules, report_map)
        linked_app = Application.get(self.linked_app._id)
        self.assertEqual(linked_app.modules[0].report_configs[0].report_id, 'mapped_id')

    def test_overwrite_app_maintain_ids(self):
        module = self.plain_master_app.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form'))

        module = self.linked_app.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form'))

        id_map_before = _get_form_id_map(self.linked_app)

        overwrite_app(self.linked_app, self.plain_master_app, {})
        self.assertEqual(
            id_map_before,
            _get_form_id_map(LinkedApplication.get(self.linked_app._id))
        )

    def test_get_master_version(self):
        self.linked_app.master = self.plain_master_app.get_id

        self.assertIsNone(self.linked_app.get_master_version())

        copy = self.plain_master_app.make_build()
        copy.save()
        self.addCleanup(copy.delete)

        self.assertIsNone(self.linked_app.get_master_version())

        self.plain_master_app.save()  # increment version number
        copy1 = self.plain_master_app.make_build()
        copy1.is_released = True
        copy1.save()
        self.addCleanup(copy1.delete)

        self.assertEqual(copy1.version, self.linked_app.get_master_version())

    def test_get_latest_master_release(self):
        self.linked_app.master = self.plain_master_app.get_id

        self.assertIsNone(self.linked_app.get_latest_master_release())

        copy = self.plain_master_app.make_build()
        copy.save()
        self.addCleanup(copy.delete)

        self.assertIsNone(self.linked_app.get_latest_master_release())

        self.plain_master_app.save()  # increment version number
        copy1 = self.plain_master_app.make_build()
        copy1.is_released = True
        copy1.save()
        self.addCleanup(copy1.delete)

        latest_master_release = self.linked_app.get_latest_master_release()
        self.assertEqual(copy1.get_id, latest_master_release.get_id)
        self.assertEqual(copy1._rev, latest_master_release._rev)

    def test_get_latest_master_release_not_permitted(self):
        self.linked_app.master = self.plain_master_app.get_id

        release = self.plain_master_app.make_build()
        release.is_released = True
        release.save()
        self.addCleanup(release.delete)

        latest_master_release = self.linked_app.get_latest_master_release()
        self.assertEqual(release.get_id, latest_master_release.get_id)

        self.domain_link.linked_domain = 'other'
        self.domain_link.save()
        get_domain_master_link.clear('domain-2')

        def _revert():
            self.domain_link.linked_domain = 'domain-2'
            self.domain_link.save()

        self.addCleanup(_revert)

        with self.assertRaises(ActionNotPermitted):
            # re-fetch to bust memoize cache
            LinkedApplication.get(self.linked_app._id).get_latest_master_release()


class TestRemoteLinkedApps(BaseLinkedAppsTest):

    @classmethod
    def setUpClass(cls):
        super(TestRemoteLinkedApps, cls).setUpClass()
        image_data = cls._get_image_data('commcare-hq-logo.png')
        cls.image = CommCareImage.get_by_data(image_data)
        cls.image.attach_data(image_data, original_filename='logo.png')
        cls.image.add_domain(cls.plain_master_app.domain)

    @classmethod
    def tearDownClass(cls):
        cls.image.delete()
        super(TestRemoteLinkedApps, cls).tearDownClass()

    @staticmethod
    def _get_image_data(filename):
        image_path = os.path.join('corehq', 'apps', 'hqwebapp', 'static', 'hqwebapp', 'images', filename)
        with open(image_path, 'r') as f:
            return f.read()

    def test_remote_app(self):
        module = self.master_app_with_report_modules.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form'))

        linked_app = _mock_pull_remote_master(
            self.master_app_with_report_modules, self.linked_app, {'id': 'mapped_id'}
        )
        master_id_map = _get_form_id_map(self.master_app_with_report_modules)
        linked_id_map = _get_form_id_map(linked_app)
        for xmlns, master_form_id in master_id_map.items():
            linked_form_id = linked_id_map[xmlns]
            self.assertEqual(
                self.master_app_with_report_modules.get_form(master_form_id).source,
                linked_app.get_form(linked_form_id).source
            )

    def test_get_missing_media_list(self):
        image_path = 'jr://file/commcare/case_list_image.jpg'
        self.master_app_with_report_modules.get_module(0).set_icon('en', image_path)

        self.master_app_with_report_modules.create_mapping(self.image, image_path, save=False)

        with patch('corehq.apps.hqmedia.models.CommCareMultimedia.get', side_effect=ResourceNotFound):
            missing_media = _get_missing_multimedia(self.master_app_with_report_modules)

        media_item = list(self.master_app_with_report_modules.multimedia_map.values())[0]
        self.assertEqual(missing_media, [('case_list_image.jpg', media_item)])

    def test_add_domain_to_media(self):
        self.image.valid_domains.remove(self.master_app_with_report_modules.domain)
        self.image.save()

        image = CommCareImage.get(self.image._id)
        self.assertNotIn(self.master_app_with_report_modules.domain, image.valid_domains)

        image_path = 'jr://file/commcare/case_list_image.jpg'
        self.master_app_with_report_modules.get_module(0).set_icon('en', image_path)
        self.master_app_with_report_modules.create_mapping(self.image, image_path, save=False)

        missing_media = _get_missing_multimedia(self.master_app_with_report_modules)
        self.assertEqual(missing_media, [])

        image = CommCareImage.get(self.image._id)
        self.assertIn(self.master_app_with_report_modules.domain, image.valid_domains)

    def test_fetch_missing_media(self):
        image_path = 'jr://file/commcare/case_list_image.jpg'
        self.master_app_with_report_modules.get_module(0).set_icon('en', image_path)
        self.master_app_with_report_modules.create_mapping(self.image, image_path, save=False)

        remote_details = RemoteLinkDetails(
            'http://localhost:8000', 'user', 'key'
        )
        data = 'this is a test'
        media_details = list(self.master_app_with_report_modules.multimedia_map.values())[0]
        media_details['multimedia_id'] = uuid.uuid4().hex
        media_details['media_type'] = 'CommCareMultimedia'
        with patch('corehq.apps.linked_domain.remote_accessors._fetch_remote_media_content') as mock:
            mock.return_value = data
            _fetch_remote_media('domain', [('case_list_image.jpg', media_details)], remote_details)

        media = CommCareMultimedia.get(media_details['multimedia_id'])
        self.addCleanup(media.delete)
        content = media.fetch_attachment(list(media.blobs.keys())[0])
        self.assertEqual(data, content)


def _mock_pull_remote_master(master_app, linked_app, report_map=None):
    master_source = convert_app_for_remote_linking(master_app)
    master_app = _convert_app_from_remote_linking_source(master_source)
    overwrite_app(linked_app, master_app, report_map or {})
    return Application.get(linked_app._id)
