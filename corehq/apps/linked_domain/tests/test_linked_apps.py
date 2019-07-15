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
from corehq.apps.app_manager.views.utils import overwrite_app, _get_form_ids_by_xmlns, update_linked_app
from corehq.apps.hqmedia.models import CommCareImage, CommCareMultimedia
from corehq.apps.linked_domain.util import convert_app_for_remote_linking
from io import open

from corehq.util.test_utils import flag_enabled, softer_assert


@flag_enabled('CAUTIOUS_MULTIMEDIA')
class BaseLinkedAppsTest(TestCase, TestXmlMixin):
    file_path = ('data',)

    @classmethod
    def setUpClass(cls):
        super(BaseLinkedAppsTest, cls).setUpClass()
        cls.domain = 'domain'
        cls.master_app_with_report_modules = Application.new_app(cls.domain, "Master Application")
        module = cls.master_app_with_report_modules.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [
            ReportAppConfig(report_id='master_report_id', header={'en': 'CommBugz'}),
        ]

        cls.plain_master_app = Application.new_app(cls.domain, "Master Application")
        cls.linked_domain = 'domain-2'
        cls.plain_master_app.linked_whitelist = [cls.linked_domain]
        cls.plain_master_app.save()

        cls.linked_app = LinkedApplication.new_app(cls.linked_domain, "Linked Application")
        cls.linked_app.save()

        cls.domain_link = DomainLink.link_domains(cls.linked_domain, cls.domain)

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
        report_map = {'master_report_id': 'mapped_id'}
        overwrite_app(self.linked_app, self.master_app_with_report_modules, report_map)
        linked_app = Application.get(self.linked_app._id)
        self.assertEqual(linked_app.modules[0].report_configs[0].report_id, 'mapped_id')

    def test_overwrite_app_maintain_ids(self):
        module = self.plain_master_app.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form').decode('utf-8'))

        module = self.linked_app.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form').decode('utf-8'))

        id_map_before = _get_form_ids_by_xmlns(self.linked_app)

        overwrite_app(self.linked_app, self.plain_master_app, {})
        self.assertEqual(
            id_map_before,
            _get_form_ids_by_xmlns(LinkedApplication.get(self.linked_app._id))
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

    def test_override_translations(self):
        translations = {'en': {'updates.check.begin': 'update?'}}

        self.linked_app.master = self.plain_master_app.get_id

        copy = self.plain_master_app.make_build()
        copy.save()
        self.addCleanup(copy.delete)

        self.plain_master_app.save()  # increment version number
        copy1 = self.plain_master_app.make_build()
        copy1.is_released = True
        copy1.save()
        self.addCleanup(copy1.delete)

        self.linked_app.linked_app_translations = translations
        self.linked_app.save()
        self.assertEqual(self.linked_app.translations, {})

        update_linked_app(self.linked_app, 'test_override_translations')
        # fetch after update to get the new version
        self.linked_app = LinkedApplication.get(self.linked_app._id)

        self.assertEqual(self.plain_master_app.translations, {})
        self.assertEqual(self.linked_app.linked_app_translations, translations)
        self.assertEqual(self.linked_app.translations, translations)

    @patch('corehq.apps.app_manager.models.get_and_assert_practice_user_in_domain', lambda x, y: None)
    def test_overrides(self):
        self.plain_master_app.practice_mobile_worker_id = "123456"
        self.plain_master_app.save()
        image_data = _get_image_data()
        image = CommCareImage.get_by_data(image_data)
        image.attach_data(image_data, original_filename='logo.png')
        image.add_domain(self.linked_app.domain)
        image.save()
        self.addCleanup(image.delete)

        image_path = "jr://file/commcare/logo/data/hq_logo_android_home.png"

        logo_refs = {
            "hq_logo_android_home": {
                "humanized_content_length": "45.4 KB",
                "icon_class": "fa fa-picture-o",
                "image_size": "448 X 332 Pixels",
                "m_id": image._id,
                "media_type": "Image",
                "path": "jr://file/commcare/logo/data/hq_logo_android_home.png",
                "uid": "3b79a76a067baf6a23a0b6978b2fb352",
                "updated": False,
                "url": "/hq/multimedia/file/CommCareImage/e3c45dd61c5593fdc5d985f0b99f6199/"
            },
        }

        self.linked_app.master = self.plain_master_app.get_id

        copy = self.plain_master_app.make_build()
        copy.save()
        self.addCleanup(copy.delete)

        self.plain_master_app.save()  # increment version number
        copy1 = self.plain_master_app.make_build()
        copy1.is_released = True
        copy1.save()
        self.addCleanup(copy1.delete)

        self.linked_app.version = 1

        self.linked_app.linked_app_logo_refs = logo_refs
        self.linked_app.create_mapping(image, image_path, save=False)
        self.linked_app.linked_app_attrs = {
            'target_commcare_flavor': 'commcare_lts',
        }
        self.linked_app.save()
        self.linked_app.practice_mobile_worker_id = 'abc123456def'
        self.assertEqual(self.linked_app.logo_refs, {})

        update_linked_app(self.linked_app, 'test_override_logos')
        # fetch after update to get the new version
        self.linked_app = LinkedApplication.get(self.linked_app._id)

        self.assertEqual(self.plain_master_app.logo_refs, {})
        self.assertEqual(self.linked_app.linked_app_logo_refs, logo_refs)
        self.assertEqual(self.linked_app.logo_refs, logo_refs)
        self.assertEqual(self.linked_app.commcare_flavor, 'commcare_lts')
        self.assertEqual(self.linked_app.linked_app_attrs, {
            'target_commcare_flavor': 'commcare_lts',
        })
        self.assertEqual(self.plain_master_app.practice_mobile_worker_id, '123456')
        self.assertEqual(self.linked_app.practice_mobile_worker_id, 'abc123456def')
        # cleanup the linked app properties
        self.linked_app.linked_app_logo_refs = {}
        self.linked_app.linked_app_attrs = {}
        self.linked_app.save()


class TestRemoteLinkedApps(BaseLinkedAppsTest):

    @classmethod
    def setUpClass(cls):
        super(TestRemoteLinkedApps, cls).setUpClass()
        image_data = _get_image_data()
        cls.image = CommCareImage.get_by_data(image_data)
        cls.image.attach_data(image_data, original_filename='logo.png')
        cls.image.add_domain(cls.plain_master_app.domain)

    @classmethod
    def tearDownClass(cls):
        cls.image.delete()
        super(TestRemoteLinkedApps, cls).tearDownClass()

    def test_remote_app(self):
        module = self.master_app_with_report_modules.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form').decode('utf-8'))

        linked_app = _mock_pull_remote_master(
            self.master_app_with_report_modules, self.linked_app, {'master_report_id': 'mapped_id'}
        )
        master_id_map = _get_form_ids_by_xmlns(self.master_app_with_report_modules)
        linked_id_map = _get_form_ids_by_xmlns(linked_app)
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

    @softer_assert()
    def test_fetch_missing_media(self):
        image_path = 'jr://file/commcare/case_list_image.jpg'
        self.master_app_with_report_modules.get_module(0).set_icon('en', image_path)
        self.master_app_with_report_modules.create_mapping(self.image, image_path, save=False)

        remote_details = RemoteLinkDetails(
            'http://localhost:8000', 'user', 'key'
        )
        data = b'this is a test: \255'  # Real data will be a binary multimedia file, so mock it with bytes, not unicode
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


def _get_image_data():
    image_path = os.path.join('corehq', 'apps', 'hqwebapp', 'static', 'hqwebapp', 'images', 'commcare-hq-logo.png')
    with open(image_path, 'rb') as f:
        return f.read()
