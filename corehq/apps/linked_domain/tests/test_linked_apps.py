import os
import uuid

from django.test.testcases import TestCase

from couchdbkit.exceptions import ResourceNotFound
from lxml import etree
from mock import patch

from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models import (
    Application,
    LinkedApplication,
    Module,
    ReportAppConfig,
    ReportModule,
    import_app,
)
from corehq.apps.app_manager.suite_xml.post_process.resources import (
    add_xform_resource_overrides,
    ResourceOverride,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.views.utils import (
    get_blank_form_xml,
    overwrite_app,
    update_linked_app,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqmedia.models import (
    CommCareAudio,
    CommCareImage,
    CommCareMultimedia,
)
from corehq.apps.linked_domain.dbaccessors import get_domain_master_link
from corehq.apps.linked_domain.exceptions import ActionNotPermitted
from corehq.apps.linked_domain.models import DomainLink, RemoteLinkDetails
from corehq.apps.linked_domain.remote_accessors import (
    _convert_app_from_remote_linking_source,
    fetch_remote_media,
)
from corehq.apps.linked_domain.util import (
    _get_missing_multimedia,
    convert_app_for_remote_linking,
)
from corehq.util.test_utils import flag_enabled, softer_assert


@flag_enabled('CAUTIOUS_MULTIMEDIA')
class BaseLinkedAppsTest(TestCase, TestXmlMixin):
    file_path = ('data',)

    @classmethod
    def setUpClass(cls):
        super(BaseLinkedAppsTest, cls).setUpClass()
        cls.domain_obj = create_domain('domain')
        cls.domain = cls.domain_obj.name
        cls.master_app_with_report_modules = Application.new_app(cls.domain, "Master Application")
        module = cls.master_app_with_report_modules.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [
            ReportAppConfig(report_id='master_report_id', header={'en': 'CommBugz'}),
        ]

        cls.linked_domain_obj = create_domain('domain-2')
        cls.linked_domain = cls.linked_domain_obj.name
        cls.master1 = Application.new_app(cls.domain, "First Master Application")
        cls.master1.linked_whitelist = [cls.linked_domain]
        cls.master1.save()

        cls.master2 = Application.new_app(cls.domain, "Second Master Application")
        cls.master2.linked_whitelist = [cls.linked_domain]
        cls.master2.save()

        cls.linked_app = LinkedApplication.new_app(cls.linked_domain, "Linked Application")
        cls.linked_app.family_id = cls.master1._id
        cls.linked_app.save()

        cls.domain_link = DomainLink.link_domains(cls.linked_domain, cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.linked_app.delete()
        cls.master1.delete()
        cls.master2.delete()
        cls.domain_link.delete()
        cls.domain_obj.delete()
        cls.linked_domain_obj.delete()
        super(BaseLinkedAppsTest, cls).tearDownClass()

    def setUp(self):
        # re-fetch app
        self.linked_app = LinkedApplication.get(self.linked_app._id)

    def tearDown(self):
        for app in (self.master1, self.master2, self.linked_app):
            for module in app.get_modules():
                app.delete_module(module.unique_id)

    def _get_form_ids_by_xmlns(self, app):
        return {form['xmlns']: form.unique_id
                for form in app.get_forms() if form.form_type != 'shadow_form'}

    def _make_master1_build(self, release):
        return self._make_build(self.master1, release)

    def _make_master2_build(self, release):
        return self._make_build(self.master2, release)

    def _make_linked_build(self):
        return self._make_build(self.linked_app, True)

    def _make_build(self, app, release):
        app.save()  # increment version number
        copy = app.make_build()
        copy.is_released = release
        copy.save()
        self.addCleanup(copy.delete)
        return copy


class TestLinkedApps(BaseLinkedAppsTest):
    def _pull_linked_app(self, upstream_app_id):
        update_linked_app(self.linked_app, upstream_app_id, 'TestLinkedApps user')
        self.linked_app = LinkedApplication.get(self.linked_app._id)

    def test_missing_ucrs(self):
        with self.assertRaises(AppEditingError):
            overwrite_app(self.linked_app, self.master_app_with_report_modules, {})

    def test_report_mapping(self):
        report_map = {'master_report_id': 'mapped_id'}
        linked_app = overwrite_app(self.linked_app, self.master_app_with_report_modules, report_map)
        self.assertEqual(linked_app.modules[0].report_configs[0].report_id, 'mapped_id')

    def test_overwrite_app_update_form_unique_ids(self):
        module = self.master1.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form').decode('utf-8'))

        module = self.linked_app.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form').decode('utf-8'))

        linked_app = overwrite_app(self.linked_app, self.master1)
        self.assertEqual(
            self._get_form_ids_by_xmlns(self.master1),
            self._get_form_ids_by_xmlns(linked_app)
        )

    def test_overwrite_app_override_form_unique_ids(self):
        module = self.master1.add_module(Module.new_module('M1', None))
        master_form = module.new_form('f1', None, self.get_xml('very_simple_form').decode('utf-8'))

        add_xform_resource_overrides(self.linked_domain, self.linked_app.get_id, {master_form.unique_id: '123'})
        overwrite_app(self.linked_app, self.master1)

        self.assertEqual(
            {master_form.xmlns: '123'},
            self._get_form_ids_by_xmlns(LinkedApplication.get(self.linked_app._id))
        )

        ResourceOverride.objects.filter(domain=self.linked_domain, app_id=self.linked_app.get_id).delete()

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_multi_master_form_attributes_and_media_versions(self, *args):
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
        master1_module = self.master1.add_module(Module.new_module('Module for master1', None))
        master1_module.new_form('Form for master1', 'en', get_blank_form_xml('Form for master1'))
        master1_map = self._get_form_ids_by_xmlns(self.master1)
        image_path = 'jr://file/commcare/photo.jpg'
        self.master1.create_mapping(CommCareImage(_id='123'), image_path)
        self.master1.get_module(0).set_icon('en', image_path)
        self._make_master1_build(True)
        master2_module = self.master2.add_module(Module.new_module('Module for master2', None))
        master2_module.new_form('Form for master2', 'en', get_blank_form_xml('Form for master2'))
        master2_map = self._get_form_ids_by_xmlns(self.master2)
        self._make_master2_build(True)

        # Pull master1, so linked app now has a form. Verify that form xmlnses match.
        self._pull_linked_app(self.master1.get_id)
        linked_master1_build1 = self._make_linked_build()
        linked_master1_build1_form = linked_master1_build1.get_module(0).get_form(0)
        linked_master1_map = self._get_form_ids_by_xmlns(self.linked_app)
        self.assertEqual(master1_map, linked_master1_map)
        original_image_version = linked_master1_build1.multimedia_map[image_path].version
        self.assertEqual(original_image_version, linked_master1_build1.version)

        # Pull master2, so linked app now has other form. Verify that form xmlnses match but unique ids do not.
        self._pull_linked_app(self.master2.get_id)
        linked_master2_build1 = self._make_linked_build()
        linked_master2_map = self._get_form_ids_by_xmlns(self.linked_app)
        linked_master2_build1_form = linked_master2_build1.get_module(0).get_form(0)
        self.assertEqual(master2_map, linked_master2_map)
        self.assertNotEqual(linked_master1_build1_form.unique_id, linked_master2_build1_form.unique_id)

        # Re-pull master1, so linked app is back to the first form, with same xmlns, unique id, and version
        linked_master1_build1 = self._make_master1_build(True)
        self._pull_linked_app(self.master1.get_id)
        linked_master1_build2 = self._make_linked_build()
        linked_master1_build2_form = linked_master1_build2.get_module(0).get_form(0)
        self.assertEqual(linked_master1_map, self._get_form_ids_by_xmlns(self.linked_app))
        self.assertEqual(linked_master1_build1_form.xmlns, linked_master1_build2_form.xmlns)
        self.assertEqual(linked_master1_build1_form.unique_id, linked_master1_build2_form.unique_id)
        self.assertEqual(linked_master1_build1_form.get_version(), linked_master1_build2_form.get_version())

        # Update form in master1 and make new linked build, which should update form version
        # Also add audio. The new audio should get the new build version, but the old image should retain
        # the version of the old app.
        wrapped = self.master1.get_module(0).get_form(0).wrapped_xform()
        wrapped.set_name("Updated form for master1")
        self.master1.get_module(0).get_form(0).source = etree.tostring(wrapped.xml, encoding="unicode")
        audio_path = 'jr://file/commcare/scream.mp3'
        self.master1.create_mapping(CommCareAudio(_id='345'), audio_path)
        self.master1.get_module(0).set_audio('en', audio_path)
        self._make_master1_build(True)
        self._pull_linked_app(self.master1.get_id)
        linked_master1_build3 = self._make_linked_build()
        linked_master1_build3_form = linked_master1_build3.get_module(0).get_form(0)
        self.assertEqual(linked_master1_build2_form.xmlns, linked_master1_build3_form.xmlns)
        self.assertEqual(linked_master1_build2_form.unique_id, linked_master1_build3_form.unique_id)
        self.assertLess(linked_master1_build2_form.get_version(), linked_master1_build3_form.get_version())
        self.assertEqual(self.linked_app.multimedia_map[image_path].version, original_image_version)
        self.assertGreater(self.linked_app.multimedia_map[audio_path].version, original_image_version)

        # Add another form to both master1 and master2. When master1 is pulled, that form should be assigned a
        # new unique id, and when master2 is pulled, it should retain that id since it has the same xmlns.
        self.master1.get_module(0).new_form('Twin form', None, self.get_xml('very_simple_form').decode('utf-8'))
        self._make_master1_build(True)
        self._pull_linked_app(self.master1.get_id)
        xmlns = self.master1.get_module(0).get_form(1).xmlns
        self.master2.get_module(0).new_form('Twin form', None, self.get_xml('very_simple_form').decode('utf-8'))
        linked_master1_build4 = self._make_linked_build()
        self._make_master2_build(True)
        self._pull_linked_app(self.master2.get_id)
        linked_master2_build2 = self._make_linked_build()
        self.assertEqual(xmlns, self.master2.get_module(0).get_form(1).xmlns)
        self.assertEqual(self._get_form_ids_by_xmlns(linked_master1_build4)[xmlns],
                         self._get_form_ids_by_xmlns(self.master1)[xmlns])
        self.assertEqual(self._get_form_ids_by_xmlns(linked_master2_build2)[xmlns],
                         self._get_form_ids_by_xmlns(self.master2)[xmlns])

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_multi_master_copy_master(self, *args):
        '''
        This tests that when a master app A is copied to A' and the linked app is pulled from A',
        the linked app's form unique ids remain consistent, and form and multimedia versions
        do NOT increment just because of the copy.
        '''

        # Add single module and form, with image, to master, and pull linked app.
        master1_module = self.master1.add_module(Module.new_module('Module for master', None))
        master1_module.new_form('Form for master', 'en', get_blank_form_xml('Form for master'))
        image_path = 'jr://file/commcare/photo.jpg'
        self.master1.create_mapping(CommCareImage(_id='123'), image_path)
        self.master1.get_module(0).set_icon('en', image_path)
        self._make_master1_build(True)
        self.linked_app.family_id = self.master1.get_id
        self.linked_app.save()
        self._pull_linked_app(self.master1.get_id)
        build1 = self._make_linked_build()

        # Make a copy of master and pull it.
        master_copy = import_app(self.master1.get_id, self.master1.domain)
        self._make_build(master_copy, True)
        self._pull_linked_app(master_copy.get_id)
        build2 = self._make_linked_build()

        # Verify form XMLNS, form version, and multimedia version all match.
        # Verify that form unique ids in linked app match ids in master app pulled from
        form1 = build1.get_module(0).get_form(0)
        form2 = build2.get_module(0).get_form(0)
        self.assertEqual(form1.xmlns, form2.xmlns)
        self.assertEqual(form1.unique_id, self.master1.get_module(0).get_form(0).unique_id)
        self.assertEqual(form2.unique_id, master_copy.get_module(0).get_form(0).unique_id)
        self.assertNotEqual(build1.version, build2.version)
        self.assertEqual(form1.get_version(), build1.version)
        self.assertEqual(form2.get_version(), build2.version)
        map_item1 = build1.multimedia_map[image_path]
        map_item2 = build2.multimedia_map[image_path]
        self.assertEqual(map_item1.unique_id, map_item2.unique_id)
        self.assertEqual(map_item1.version, map_item2.version)

    def test_get_latest_master_release(self):
        self.assertIsNone(self.linked_app.get_latest_master_release(self.master1.get_id))

        self._make_master1_build(False)
        self.assertIsNone(self.linked_app.get_latest_master_release(self.master1.get_id))

        self._make_master1_build(True)
        master1_copy2 = self._make_master1_build(True)

        latest_master_release = self.linked_app.get_latest_master_release(self.master1.get_id)
        self.assertEqual(master1_copy2.get_id, latest_master_release.get_id)
        self.assertEqual(master1_copy2._rev, latest_master_release._rev)

        master2_copy1 = self._make_master2_build(True)
        latest_master1_release = self.linked_app.get_latest_master_release(self.master1.get_id)
        latest_master2_release = self.linked_app.get_latest_master_release(self.master2.get_id)
        self.assertEqual(master1_copy2.get_id, latest_master1_release.get_id)
        self.assertEqual(master2_copy1.get_id, latest_master2_release.get_id)

    def test_incremental_versioning(self):
        original_master_version = self.master1.version or 0
        original_linked_version = self.linked_app.version or 0

        # Make a few versions of master app
        self._make_master1_build(True)
        self._make_master1_build(True)
        self._make_master1_build(True)
        current_master = self._make_master1_build(True)

        self._pull_linked_app(self.master1.get_id)
        self.assertEqual(current_master.version, original_master_version + 4)
        self.assertEqual(self.linked_app.version, original_linked_version + 1)

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_multi_master_fields(self, *args):
        original_master1_version = self.master1.version or 0
        original_master2_version = self.master2.version or 0

        # Make a few versions of master apps
        self._make_master1_build(True)
        self._make_master1_build(True)
        self._make_master1_build(True)
        self._make_master1_build(True)
        self._make_master2_build(True)
        self._make_master2_build(True)
        self._make_master2_build(True)

        self._pull_linked_app(self.master1.get_id)
        self.assertEqual(self.linked_app.upstream_app_id, self.master1.get_id)
        self.assertEqual(self.linked_app.upstream_version, original_master1_version + 4)

        self._pull_linked_app(self.master2.get_id)
        self.assertEqual(self.linked_app.upstream_app_id, self.master2.get_id)
        self.assertEqual(self.linked_app.upstream_version, original_master2_version + 3)

    def test_get_latest_build_from_upstream(self):
        # Make build of master1, pull linked app, and make linked app build
        self._make_master1_build(True)
        self._pull_linked_app(self.master1.get_id)
        linked_build1 = self._make_linked_build()

        # Make several builds of master2, each also pulled to linked app and built there
        self._make_master2_build(True)
        self._make_master2_build(True)
        self._pull_linked_app(self.master2.get_id)
        linked_build2 = self._make_linked_build()
        self._make_master2_build(True)
        self._make_master2_build(True)
        self._pull_linked_app(self.master2.get_id)
        linked_build3 = self._make_linked_build()

        previous_master2_version = linked_build3.get_latest_build_from_upstream(self.master2.get_id)
        self.assertEqual(previous_master2_version.upstream_app_id, self.master2.get_id)
        self.assertEqual(previous_master2_version.get_id, linked_build2.get_id)

        previous_master1_version = linked_build3.get_latest_build_from_upstream(self.master1.get_id)
        self.assertEqual(previous_master1_version.upstream_app_id, self.master1.get_id)
        self.assertEqual(previous_master1_version.get_id, linked_build1.get_id)

    def test_get_latest_master_release_not_permitted(self):
        release = self._make_master1_build(True)
        latest_master_release = self.linked_app.get_latest_master_release(self.master1.get_id)
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
            LinkedApplication.get(self.linked_app._id).get_latest_master_release(self.master1.get_id)

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_override_translations(self, *args):
        translations = {'en': {'updates.check.begin': 'update?'}}

        self._make_master1_build(True)
        self._make_master1_build(True)

        self.linked_app.linked_app_translations = translations
        self.linked_app.save()
        self.assertEqual(self.linked_app.translations, {})

        self._pull_linked_app(self.master1.get_id)
        self.linked_app = LinkedApplication.get(self.linked_app._id)
        self.assertEqual(self.master1.translations, {})
        self.assertEqual(self.linked_app.linked_app_translations, translations)
        self.assertEqual(self.linked_app.translations, translations)

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    @patch('corehq.apps.app_manager.models.get_and_assert_practice_user_in_domain', lambda x, y: None)
    def test_overrides(self, *args):
        self.master1.practice_mobile_worker_id = "123456"
        self.master1.save()
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

        self._make_master1_build(True)
        self._make_master1_build(True)

        self.linked_app.version = 1

        self.linked_app.linked_app_logo_refs = logo_refs
        self.linked_app.create_mapping(image, image_path, save=False)
        self.linked_app.linked_app_attrs = {
            'target_commcare_flavor': 'commcare_lts',
        }
        self.linked_app.save()
        self.linked_app.practice_mobile_worker_id = 'abc123456def'
        self.assertEqual(self.linked_app.logo_refs, {})

        self._pull_linked_app(self.master1.get_id)
        self.assertEqual(self.master1.logo_refs, {})
        self.assertEqual(self.linked_app.linked_app_logo_refs, logo_refs)
        self.assertEqual(self.linked_app.logo_refs, logo_refs)
        self.assertEqual(self.linked_app.commcare_flavor, 'commcare_lts')
        self.assertEqual(self.linked_app.linked_app_attrs, {
            'target_commcare_flavor': 'commcare_lts',
        })
        self.assertEqual(self.master1.practice_mobile_worker_id, '123456')
        self.assertEqual(self.linked_app.practice_mobile_worker_id, 'abc123456def')
        # cleanup the linked app properties
        self.linked_app.linked_app_logo_refs = {}
        self.linked_app.linked_app_attrs = {}
        self.linked_app.save()

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_update_from_specific_build(self, *args):
        master_app = Application.new_app(self.domain, "Master Application")
        master_app.linked_whitelist = [self.linked_domain]
        master_app.save()
        self.addCleanup(master_app.delete)

        linked_app = LinkedApplication.new_app(self.linked_domain, "Linked Application")
        linked_app.save()
        self.addCleanup(linked_app.delete)

        master_app.add_module(Module.new_module('M1', None))
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
        cls.image.add_domain(cls.master1.domain)

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
        master_id_map = self._get_form_ids_by_xmlns(self.master_app_with_report_modules)
        linked_id_map = self._get_form_ids_by_xmlns(linked_app)
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


class TestLinkedAppsWithShadowForms(TestCase):
    maxDiff = None

    def test_overwrite_app_with_shadow_forms(self):
        upstream_app = self._make_app_with_shadow_forms()
        linked_app = self._make_linked_app(upstream_app.domain)

        linked_app = overwrite_app(linked_app, upstream_app, {})
        original_forms = sorted(linked_app.get_forms(), key=lambda form: form.name['en'])

        linked_app = overwrite_app(linked_app, upstream_app, {})
        updated_forms = sorted(linked_app.get_forms(), key=lambda form: form.name['en'])

        for original, updated in zip(original_forms, updated_forms):
            self.assertEqual(original.name, updated.name)
            self.assertEqual(original.xmlns, updated.xmlns)
            if original.form_type != 'shadow_form':
                self.assertEqual(original.unique_id, updated.unique_id)

    def _make_app_with_shadow_forms(self):
        factory = AppFactory('upstream', "Upstream App", include_xmlns=True)
        module1, form1 = factory.new_advanced_module('M1', 'casetype')
        factory.new_form(module1)
        module2, form2 = factory.new_advanced_module('M2', 'casetype')
        factory.new_form(module2)
        self._make_shadow_form(factory, 'M3', form1)
        self._make_shadow_form(factory, 'M4', form2)
        factory.app.save()
        self.addCleanup(factory.app.delete)
        # the test form names are unique
        form_names = [f.name['en'] for f in factory.app.get_forms()]
        self.assertEqual(len(form_names), len(set(form_names)))
        return factory.app

    @staticmethod
    def _make_shadow_form(factory, module_name, parent_form):
        module = factory.new_advanced_module(module_name, 'casetype', with_form=False)
        shadow_form = factory.new_shadow_form(module)
        shadow_form.shadow_parent_form_id = parent_form.unique_id

    def _make_linked_app(self, upstream_domain):
        linked_app = LinkedApplication.new_app('downstream', "Linked Application")
        linked_app.save()
        domain_link = DomainLink.link_domains('downstream', upstream_domain)
        self.addCleanup(linked_app.delete)
        self.addCleanup(domain_link.delete)
        return linked_app
