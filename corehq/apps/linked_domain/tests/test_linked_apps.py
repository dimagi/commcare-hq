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
    Module,
    LinkedApplication,
    ReportAppConfig,
    ReportModule,
    import_app,
)
from corehq.apps.linked_domain.dbaccessors import get_domain_master_link
from corehq.apps.linked_domain.exceptions import ActionNotPermitted
from corehq.apps.linked_domain.models import DomainLink, RemoteLinkDetails
from corehq.apps.linked_domain.remote_accessors import (
    _convert_app_from_remote_linking_source,
    fetch_remote_media,
)
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.views.utils import (
    get_blank_form_xml,
    overwrite_app,
    update_linked_app,
    _get_form_ids_by_xmlns,
)
from corehq.apps.hqmedia.models import CommCareAudio, CommCareImage, CommCareMultimedia
from corehq.apps.linked_domain.util import (
    convert_app_for_remote_linking,
    _get_missing_multimedia,
)
from lxml import etree
from io import open

from corehq.util.test_utils import flag_enabled, softer_assert


@flag_enabled('CAUTIOUS_MULTIMEDIA')
class BaseLinkedAppsTest(TestCase, TestXmlMixin):
    file_path = ('data',)

    @classmethod
    def setUpClass(cls):
        super(BaseLinkedAppsTest, cls).setUpClass()
        cls.domain = 'domain'
        cls.linked_domain = 'domain-2'
        cls.domain_link = DomainLink.link_domains(cls.linked_domain, cls.domain)

        # The class provides two master apps: one with a single basic module (no forms)
        # and one with a report module
        cls.plain_master = Application.new_app(cls.domain, "Master Application")
        cls.plain_master.add_module(Module.new_module('M1', None))
        cls.plain_master.save()
        cls.master_with_reports = Application.new_app(cls.domain, "Master Application with Reports")
        module = cls.master_with_reports.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [
            ReportAppConfig(report_id='master_report_id', header={'en': 'CommBugz'}),
        ]
        cls.master_with_reports.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_link.delete()
        cls.plain_master.delete()
        cls.master_with_reports.delete()
        super(BaseLinkedAppsTest, cls).tearDownClass()

    # Add a new master app with a single basic module and no forms
    def _create_master_app(self, name="Master Application"):
        app = self._create_app(self.domain, Application, name)
        app.add_module(Module.new_module('M1', None))
        return app

    def _create_linked_app(self):
        return self._create_app(self.linked_domain, LinkedApplication, "Linked Application")

    def _create_app(self, domain, app_class, name):
        app = app_class.new_app(domain, name)
        self.addCleanup(app.delete)
        app.save()  # save at least once, otherwise cleanup will fail
        return app


class TestLinkedApps(BaseLinkedAppsTest):
    def _make_build(self, app, release):
        app.save()  # increment version number
        copy = app.make_build()
        copy.is_released = release
        copy.save()
        self.addCleanup(copy.delete)
        return copy

    def _pull_linked_app(self, linked_app, upstream_app_id):
        update_linked_app(linked_app, upstream_app_id, 'TestLinkedApps user')
        return LinkedApplication.get(linked_app._id)

    def test_missing_ucrs(self):
        linked_app = self._create_linked_app()
        with self.assertRaises(AppEditingError):
            overwrite_app(linked_app, self.master_with_reports, {})

    def test_report_mapping(self):
        linked_app = self._create_linked_app()
        report_map = {'master_report_id': 'mapped_id'}
        overwrite_app(linked_app, self.master_with_reports, report_map)
        linked_app = Application.get(linked_app._id)
        self.assertEqual(linked_app.modules[0].report_configs[0].report_id, 'mapped_id')

    def test_overwrite_app_maintain_form_unique_ids(self):
        master_app = self._create_master_app()
        master_app.get_module(0).new_form('f1', None, self.get_xml('very_simple_form').decode('utf-8'))

        linked_app = self._create_linked_app()
        module = linked_app.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form').decode('utf-8'))

        id_map_before = _get_form_ids_by_xmlns(linked_app)

        overwrite_app(linked_app, master_app, {})
        self.assertEqual(
            id_map_before,
            _get_form_ids_by_xmlns(LinkedApplication.get(linked_app._id))
        )

    def test_multi_master_form_attributes_and_media_versions(self):
        '''
        This tests a few things related to pulling a linked app from multiple master apps,
        particularly interleaving pulls (pulling master A, then master B, then master A again):
        - Form versions should not change unless the form content changed
        - Form unique ids should be different from the master they came from but consistent across
          versions of the linked app that come from that master.
        - If a new form is added to multiple masters, that form's unique id should be the same
          across all versions of the linked app that pull from any of those masters - that is,
          each XMLNS in the linked app should correspond to one and only one form unique id.
        - Multimedia versions should not change, but should be consistent with the version
          of the linked app where they were introduced.
        '''

        # Add single module and form to both master1 and master2.
        # The module in master1 will also be used for multimedia testing.
        master1 = self._create_master_app("Master 1")
        master1.get_module(0).new_form('Form for master1', 'en', get_blank_form_xml('Form for master1'))
        master1_map = _get_form_ids_by_xmlns(master1)
        image_path = 'jr://file/commcare/photo.jpg'
        master1.create_mapping(CommCareImage(_id='123'), image_path)
        master1.get_module(0).set_icon('en', image_path)
        self._make_build(master1, True)
        master2 = self._create_master_app("Master 2")
        master2.get_module(0).new_form('Form for master2', 'en', get_blank_form_xml('Form for master2'))
        master2_map = _get_form_ids_by_xmlns(master2)
        self._make_build(master2, True)

        # Pull master1, so linked app now has a form. Verify that form xmlnses match but unique ids do not.
        linked_app = self._create_linked_app()
        linked_app = self._pull_linked_app(linked_app, master1.get_id)
        linked_master1_build1 = self._make_build(linked_app, True)
        linked_master1_build1_form = linked_master1_build1.get_module(0).get_form(0)
        linked_master1_map = _get_form_ids_by_xmlns(linked_app)
        self.assertEqual(set(master1_map.keys()), set(linked_master1_map.keys()))
        self.assertNotEqual(set(master1_map.values()), set(linked_master1_map.values()))
        original_image_version = linked_app.multimedia_map[image_path].version
        self.assertEqual(original_image_version, linked_app.version)

        # Pull master2, so linked app now has other form. Verify that form xmlnses match but unique ids do not.
        linked_app = self._pull_linked_app(linked_app, master2.get_id)
        linked_master2_build1 = self._make_build(linked_app, True)
        linked_master2_map = _get_form_ids_by_xmlns(linked_app)
        linked_master2_build1_form = linked_master2_build1.get_module(0).get_form(0)
        self.assertEqual(set(master2_map.keys()), set(linked_master2_map.keys()))
        self.assertNotEqual(set(master2_map.values()), set(linked_master2_map.values()))
        self.assertNotEqual(linked_master1_build1_form.unique_id, linked_master2_build1_form.unique_id)

        # Re-pull master1, so linked app is back to the first form, with same xmlns, unique id, and version
        linked_master1_build1 = self._make_build(master1, True)
        linked_app = self._pull_linked_app(linked_app, master1.get_id)
        linked_master1_build2 = self._make_build(linked_app, True)
        linked_master1_build2_form = linked_master1_build2.get_module(0).get_form(0)
        self.assertEqual(linked_master1_map, _get_form_ids_by_xmlns(linked_app))
        self.assertEqual(linked_master1_build1_form.xmlns, linked_master1_build2_form.xmlns)
        self.assertEqual(linked_master1_build1_form.unique_id, linked_master1_build2_form.unique_id)
        self.assertEqual(linked_master1_build1_form.get_version(), linked_master1_build2_form.get_version())

        # Update form in master1 and make new linked build, which should update form version
        # Also add audio. The new audio should get the new build version, but the old image should retain
        # the version of the old app.
        wrapped = master1.get_module(0).get_form(0).wrapped_xform()
        wrapped.set_name("Updated form for master1")
        master1.get_module(0).get_form(0).source = etree.tostring(wrapped.xml, encoding="unicode")
        audio_path = 'jr://file/commcare/scream.mp3'
        master1.create_mapping(CommCareAudio(_id='345'), audio_path)
        master1.get_module(0).set_audio('en', audio_path)
        self._make_build(master1, True)
        linked_app = self._pull_linked_app(linked_app, master1.get_id)
        linked_master1_build3 = self._make_build(linked_app, True)
        linked_master1_build3_form = linked_master1_build3.get_module(0).get_form(0)
        self.assertEqual(linked_master1_build2_form.xmlns, linked_master1_build3_form.xmlns)
        self.assertEqual(linked_master1_build2_form.unique_id, linked_master1_build3_form.unique_id)
        self.assertLess(linked_master1_build2_form.get_version(), linked_master1_build3_form.get_version())
        self.assertEqual(linked_app.multimedia_map[image_path].version, original_image_version)
        self.assertGreater(linked_app.multimedia_map[audio_path].version, original_image_version)

        # Add another form to both master1 and master2. When master1 is pulled, that form should be assigned a
        # new unique id, and when master2 is pulled, it should retain that id since it has the same xmlns.
        master1.get_module(0).new_form('Twin form', None, self.get_xml('very_simple_form').decode('utf-8'))
        self._make_build(master1, True)
        linked_app = self._pull_linked_app(linked_app, master1.get_id)
        xmlns = master1.get_module(0).get_form(1).xmlns
        master2.get_module(0).new_form('Twin form', None, self.get_xml('very_simple_form').decode('utf-8'))
        linked_master1_build4 = self._make_build(linked_app, True)
        self._make_build(master2, True)
        linked_app = self._pull_linked_app(linked_app, master2.get_id)
        linked_master2_build2 = self._make_build(linked_app, True)
        self.assertEqual(xmlns, master2.get_module(0).get_form(1).xmlns)
        self.assertEqual(_get_form_ids_by_xmlns(linked_master1_build4)[xmlns],
                         _get_form_ids_by_xmlns(linked_master2_build2)[xmlns])

    def test_multi_master_copy_master(self):
        '''
        This tests that when a master app A is copied to A' and the linked app is pulled from A',
        the linked app's form unique ids remain consistent, and form and multimedia versions
        do NOT increment just because of the copy.
        '''

        # Add single module and form, with image, to master, and pull linked app.
        master_app = self._create_master_app()
        master_app.get_module(0).new_form('Form for master', 'en', get_blank_form_xml('Form for master'))
        image_path = 'jr://file/commcare/photo.jpg'
        master_app.create_mapping(CommCareImage(_id='123'), image_path)
        master_app.get_module(0).set_icon('en', image_path)
        self._make_build(master_app, True)

        linked_app = self._create_linked_app()
        linked_app.family_id = master_app.get_id
        linked_app.save()
        linked_app = self._pull_linked_app(linked_app, master_app.get_id)
        build1 = self._make_build(linked_app, True)

        # Make a copy of master and pull it.
        master_copy = import_app(master_app.get_id, master_app.domain)
        self._make_build(master_copy, True)
        linked_app = self._pull_linked_app(linked_app, master_copy.get_id)
        build2 = self._make_build(linked_app, True)

        # Verify form XMLNS, form unique id, form version, and multimedia version all match.
        form1 = build1.get_module(0).get_form(0)
        form2 = build2.get_module(0).get_form(0)
        self.assertEqual(form1.xmlns, form2.xmlns)
        self.assertEqual(form1.unique_id, form2.unique_id)
        self.assertNotEqual(build1.version, build2.version)
        self.assertEqual(form1.get_version(), form2.get_version())
        map_item1 = build1.multimedia_map[image_path]
        map_item2 = build2.multimedia_map[image_path]
        self.assertEqual(map_item1.unique_id, map_item2.unique_id)
        self.assertEqual(map_item1.version, map_item2.version)

    def test_get_latest_master_release(self):
        master1 = self._create_master_app("Master 1")
        linked_app = self._create_linked_app()
        self.assertIsNone(linked_app.get_latest_master_release(master1.get_id))

        self._make_build(master1, False)
        self.assertIsNone(linked_app.get_latest_master_release(master1.get_id))

        self._make_build(master1, True)
        master1_copy2 = self._make_build(master1, True)

        latest_master_release = linked_app.get_latest_master_release(master1.get_id)
        self.assertEqual(master1_copy2.get_id, latest_master_release.get_id)
        self.assertEqual(master1_copy2._rev, latest_master_release._rev)

        master2 = self._create_master_app("Master 2")
        master2_copy1 = self._make_build(master2, True)
        latest_master1_release = linked_app.get_latest_master_release(master1.get_id)
        latest_master2_release = linked_app.get_latest_master_release(master2.get_id)
        self.assertEqual(master1_copy2.get_id, latest_master1_release.get_id)
        self.assertEqual(master2_copy1.get_id, latest_master2_release.get_id)

    def test_incremental_versioning(self):
        linked_app = self._create_linked_app()
        original_master_version = self.plain_master.version or 0
        original_linked_version = linked_app.version or 0

        # Make a few versions of master app
        self._make_build(self.plain_master, True)
        self._make_build(self.plain_master, True)
        self._make_build(self.plain_master, True)
        current_master = self._make_build(self.plain_master, True)

        linked_app = self._pull_linked_app(linked_app, self.plain_master.get_id)
        self.assertEqual(current_master.version, original_master_version + 4)
        self.assertEqual(linked_app.version, original_linked_version + 1)

    def test_multi_master_fields(self):
        master1 = self._create_master_app("Master 1")
        master2 = self._create_master_app("Master 2")
        linked_app = self._create_linked_app()
        original_master1_version = master1.version or 0
        original_master2_version = master2.version or 0

        # Make a few versions of master apps
        self._make_build(master1, True)
        self._make_build(master1, True)
        self._make_build(master1, True)
        self._make_build(master1, True)
        self._make_build(master2, True)
        self._make_build(master2, True)
        self._make_build(master2, True)

        linked_app = self._pull_linked_app(linked_app, master1.get_id)
        self.assertEqual(linked_app.upstream_app_id, master1.get_id)
        self.assertEqual(linked_app.upstream_version, original_master1_version + 4)

        linked_app = self._pull_linked_app(linked_app, master2.get_id)
        self.assertEqual(linked_app.upstream_app_id, master2.get_id)
        self.assertEqual(linked_app.upstream_version, original_master2_version + 3)

    def test_get_latest_build_from_upstream(self):
        # Make build of master1, pull linked app, and make linked app build
        master1 = self._create_master_app("Master 1")
        master2 = self._create_master_app("Master 2")
        linked_app = self._create_linked_app()
        self._make_build(master1, True)
        linked_app = self._pull_linked_app(linked_app, master1.get_id)
        linked_build1 = self._make_build(linked_app, True)

        # Make several builds of master2, each also pulled to linked app and built there
        self._make_build(master2, True)
        self._make_build(master2, True)
        linked_app = self._pull_linked_app(linked_app, master2.get_id)
        linked_build2 = self._make_build(linked_app, True)
        self._make_build(master2, True)
        self._make_build(master2, True)
        linked_app = self._pull_linked_app(linked_app, master2.get_id)
        linked_build3 = self._make_build(linked_app, True)

        previous_master2_version = linked_build3.get_latest_build_from_upstream(master2.get_id)
        self.assertEqual(previous_master2_version.upstream_app_id, master2.get_id)
        self.assertEqual(previous_master2_version.get_id, linked_build2.get_id)

        previous_master1_version = linked_build3.get_latest_build_from_upstream(master1.get_id)
        self.assertEqual(previous_master1_version.upstream_app_id, master1.get_id)
        self.assertEqual(previous_master1_version.get_id, linked_build1.get_id)

    def test_get_latest_master_release_not_permitted(self):
        linked_app = self._create_linked_app()
        release = self._make_build(self.plain_master, True)
        latest_master_release = linked_app.get_latest_master_release(self.plain_master.get_id)
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
            LinkedApplication.get(linked_app._id).get_latest_master_release(self.plain_master.get_id)

    def test_override_translations(self):
        translations = {'en': {'updates.check.begin': 'update?'}}

        linked_app = self._create_linked_app()
        self._make_build(self.plain_master, True)
        self._make_build(self.plain_master, True)

        linked_app.linked_app_translations = translations
        linked_app.save()
        self.assertEqual(linked_app.translations, {})

        linked_app = self._pull_linked_app(linked_app, self.plain_master.get_id)
        linked_app = LinkedApplication.get(linked_app._id)
        self.assertEqual(self.plain_master.translations, {})
        self.assertEqual(linked_app.linked_app_translations, translations)
        self.assertEqual(linked_app.translations, translations)

    @patch('corehq.apps.app_manager.models.get_and_assert_practice_user_in_domain', lambda x, y: None)
    def test_overrides(self):
        master_app = self._create_master_app()
        linked_app = self._create_linked_app()
        master_app.practice_mobile_worker_id = "123456"
        master_app.save()
        image_data = _get_image_data()
        image = CommCareImage.get_by_data(image_data)
        image.attach_data(image_data, original_filename='logo.png')
        image.add_domain(linked_app.domain)
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

        self._make_build(master_app, True)
        self._make_build(master_app, True)

        linked_app.version = 1

        linked_app.linked_app_logo_refs = logo_refs
        linked_app.create_mapping(image, image_path, save=False)
        linked_app.linked_app_attrs = {
            'target_commcare_flavor': 'commcare_lts',
        }
        linked_app.save()
        linked_app.practice_mobile_worker_id = 'abc123456def'
        self.assertEqual(linked_app.logo_refs, {})

        linked_app = self._pull_linked_app(linked_app, master_app.get_id)
        self.assertEqual(master_app.logo_refs, {})
        self.assertEqual(linked_app.linked_app_logo_refs, logo_refs)
        self.assertEqual(linked_app.logo_refs, logo_refs)
        self.assertEqual(linked_app.commcare_flavor, 'commcare_lts')
        self.assertEqual(linked_app.linked_app_attrs, {
            'target_commcare_flavor': 'commcare_lts',
        })
        self.assertEqual(master_app.practice_mobile_worker_id, '123456')
        self.assertEqual(linked_app.practice_mobile_worker_id, 'abc123456def')

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_update_from_specific_build(self, *args):
        master_app = Application.new_app(self.domain, "Master Application")
        master_app.linked_whitelist = [self.linked_domain]
        master_app.save()
        self.addCleanup(master_app.delete)

        linked_app = LinkedApplication.new_app(self.linked_domain, "Linked Application")
        linked_app.save()
        self.addCleanup(linked_app.delete)

        master_app = self._create_master_app()
        copy1 = self._make_build(master_app, True)

        master_app.add_module(Module.new_module('M2', None))
        master_app.save()  # increment version number
        self._make_build(master_app, True)

        update_linked_app(linked_app, copy1, 'test_update_from_specific_build')
        linked_app = LinkedApplication.get(linked_app._id)
        self.assertEqual(len(linked_app.modules), 1)
        self.assertEqual(linked_app.version, copy1.version)


class TestRemoteLinkedApps(BaseLinkedAppsTest):

    @classmethod
    def setUpClass(cls):
        super(TestRemoteLinkedApps, cls).setUpClass()
        image_data = _get_image_data()
        cls.image = CommCareImage.get_by_data(image_data)
        cls.image.attach_data(image_data, original_filename='logo.png')
        cls.image.add_domain(cls.plain_master.domain)

    @classmethod
    def tearDownClass(cls):
        cls.image.delete()
        super(TestRemoteLinkedApps, cls).tearDownClass()

    def test_remote_app(self):
        master_app = self._create_master_app()
        master_app.get_module(0).new_form('f1', None, self.get_xml('very_simple_form').decode('utf-8'))

        linked_app = self._create_linked_app()
        linked_app = _mock_pull_remote_master(
            master_app, linked_app, {'master_report_id': 'mapped_id'}
        )
        master_id_map = _get_form_ids_by_xmlns(master_app)
        linked_id_map = _get_form_ids_by_xmlns(linked_app)
        for xmlns, master_form_id in master_id_map.items():
            linked_form_id = linked_id_map[xmlns]
            self.assertEqual(
                master_app.get_form(master_form_id).source,
                linked_app.get_form(linked_form_id).source
            )

    def test_get_missing_media_list(self):
        master_app = self._create_master_app()
        image_path = 'jr://file/commcare/case_list_image.jpg'
        master_app.get_module(0).set_icon('en', image_path)

        master_app.create_mapping(self.image, image_path, save=False)

        with patch('corehq.apps.hqmedia.models.CommCareMultimedia.get', side_effect=ResourceNotFound):
            missing_media = _get_missing_multimedia(master_app)

        media_item = list(master_app.multimedia_map.values())[0]
        self.assertEqual(missing_media, [('case_list_image.jpg', media_item)])

    def test_add_domain_to_media(self):
        master_app = self._create_master_app()
        self.image.valid_domains.remove(master_app.domain)
        self.image.save()

        image = CommCareImage.get(self.image._id)
        self.assertNotIn(master_app.domain, image.valid_domains)

        image_path = 'jr://file/commcare/case_list_image.jpg'
        master_app.get_module(0).set_icon('en', image_path)
        master_app.create_mapping(self.image, image_path, save=False)

        missing_media = _get_missing_multimedia(master_app)
        self.assertEqual(missing_media, [])

        image = CommCareImage.get(self.image._id)
        self.assertIn(master_app.domain, image.valid_domains)

    @softer_assert()
    def test_fetch_missing_media(self):
        image_path = 'jr://file/commcare/case_list_image.jpg'
        master_app = self._create_master_app()
        master_app.get_module(0).set_icon('en', image_path)
        master_app.create_mapping(self.image, image_path, save=False)

        remote_details = RemoteLinkDetails(
            'http://localhost:8000', 'user', 'key'
        )
        data = b'this is a test: \255'  # Real data will be a binary multimedia file, so mock it with bytes, not unicode
        media_details = list(master_app.multimedia_map.values())[0]
        media_details['multimedia_id'] = uuid.uuid4().hex
        media_details['media_type'] = 'CommCareMultimedia'
        with patch('corehq.apps.linked_domain.remote_accessors._fetch_remote_media_content') as mock:
            mock.return_value = data
            fetch_remote_media('domain', [('case_list_image.jpg', media_details)], remote_details)

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
