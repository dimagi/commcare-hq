# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from mock import patch
from copy import deepcopy

from django.test import SimpleTestCase

from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.tests.util import parse_normalize
from corehq.apps.hqmedia.models import CommCareImage
from corehq.util.test_utils import flag_enabled


class MediaVersionTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def _get_linked_app_json(self):
        linked_app_doc = self.get_json('app')
        linked_app_doc['doc_type'] = 'LinkedApplication'
        return linked_app_doc

    @staticmethod
    def _get_media_resources_versions(Xml):
        parsedXml = parse_normalize(Xml, to_string=False)
        return {resource_node.get('id'): resource_node.get('version')
                for resource_node in parsedXml.findall("media/resource")}

    @staticmethod
    def _add_image_media(app):
        image_path = 'jr://file/commcare/case_list_image.jpg'
        app.get_module(0).case_list_form.set_icon('en', image_path)
        app.create_mapping(CommCareImage(_id='123'), image_path, save=False)

    @patch('corehq.apps.app_manager.models.ApplicationBase.get_previous_version')
    def test_version_reset_on_revert_for_master(self, previous_version_mock):
        previous_version_mock.return_value = None

        # multimedia added
        app_v1 = wrap_app(deepcopy(self.get_json('app')))
        self._add_image_media(app_v1)
        app_v1.set_media_versions()
        self.assertEqual(app_v1.multimedia_map['jr://file/commcare/case_list_image.jpg'].version, 1)

        # multimedia removed
        app_v2 = wrap_app(deepcopy(self.get_json('app')))
        app_v2.version = 2
        previous_version_mock.return_value = app_v1
        app_v2.set_media_versions()
        self.assertFalse('jr://file/commcare/case_list_image.jpg' in app_v2.multimedia_map)

        # v3 is a revert to v1, multimedia added back
        app_v3 = wrap_app(app_v1.to_json())
        app_v3.version = 3
        previous_version_mock.return_value = app_v2
        app_v3.set_media_versions(version_reverted_to=1)

        # version bumped to current version for media re-added in the revert but missing in previous version
        self.assertEqual(app_v3.multimedia_map['jr://file/commcare/case_list_image.jpg'].version, 3)

        # assert calls
        self.assertEqual(previous_version_mock.call_count, 3)

    @flag_enabled('ICDS')
    @patch('corehq.apps.app_manager.models.wrap_app')
    @patch('corehq.apps.app_manager.models.get_build_doc_by_version')
    @patch('corehq.apps.app_manager.models.ApplicationBase.get_previous_version')
    def test_version_not_reset_on_revert_for_master(self, previous_version_mock, build_doc_mock, wrap_app_mock):
        previous_version_mock.return_value = None
        build_doc_mock.return_value = 'Some Doc'

        # multimedia added
        app_v1 = wrap_app(self.get_json('app'))
        self._add_image_media(app_v1)
        app_v1.set_media_versions()
        self.assertEqual(app_v1.multimedia_map['jr://file/commcare/case_list_image.jpg'].version, 1)

        # multimedia removed
        app_v2 = wrap_app(self.get_json('app'))
        app_v2.version = 2
        previous_version_mock.return_value = app_v1
        app_v2.set_media_versions()
        self.assertFalse('jr://file/commcare/case_list_image.jpg' in app_v2.multimedia_map)

        # v3 is a revert to v1, multimedia added back
        app_v3 = wrap_app(app_v1.to_json())
        app_v3.version = 3
        wrap_app_mock.return_value = app_v1
        app_v3.set_media_versions(version_reverted_to=1)

        # version NOT bumped for media re-added in the revert but missing in previous version
        self.assertEqual(app_v3.multimedia_map['jr://file/commcare/case_list_image.jpg'].version, 1)

        # assert calls
        build_doc_mock.assert_called_once()
        wrap_app_mock.assert_called_once_with('Some Doc')
        self.assertEqual(previous_version_mock.call_count, 2)

    @patch('corehq.apps.app_manager.models.wrap_app')
    @patch('corehq.apps.app_manager.models.get_build_doc_by_version')
    @patch('corehq.apps.app_manager.models.ApplicationBase.get_previous_version')
    def test_version_reset_on_revert_for_linked(self, previous_version_mock, build_doc_mock, wrap_app_mock):
        previous_version_mock.return_value = None

        # multimedia added
        linked_app_v1 = wrap_app(self._get_linked_app_json())
        linked_app_v1.version = 100
        self._add_image_media(linked_app_v1)
        linked_app_v1.set_media_versions()
        self.assertEqual(linked_app_v1.multimedia_map['jr://file/commcare/case_list_image.jpg'].version, 100)

        # multimedia removed
        linked_app_v2 = wrap_app(self._get_linked_app_json())
        linked_app_v2.version = 200
        previous_version_mock.return_value = linked_app_v1
        linked_app_v2.set_media_versions()
        self.assertFalse('jr://file/commcare/case_list_image.jpg' in linked_app_v2.multimedia_map)

        # set up updated app which would act like a revert to previous version, multimedia added back
        linked_app_v3_doc = deepcopy(linked_app_v1.to_json())
        linked_app_v3_doc['version'] = 400
        linked_app_v3 = wrap_app(linked_app_v3_doc)
        previous_version_mock.return_value = linked_app_v2
        linked_app_v3.set_media_versions()

        # version bumped to current version for media re-added in the revert but missing in previous version
        self.assertEqual(linked_app_v3.multimedia_map['jr://file/commcare/case_list_image.jpg'].version, 400)

        # ensure expected calls
        build_doc_mock.assert_not_called()
        wrap_app_mock.assert_not_called()
        self.assertEqual(previous_version_mock.call_count, 3)

    @flag_enabled('ICDS')
    @patch('corehq.apps.app_manager.models.wrap_app')
    @patch('corehq.apps.app_manager.models.get_build_doc_by_version')
    @patch('corehq.apps.app_manager.models.ApplicationBase.get_previous_version')
    def test_version_not_reset_on_revert_for_linked(self, previous_version_mock, build_doc_mock, wrap_app_mock):
        previous_version_mock.return_value = None

        # multimedia added
        linked_app_v1 = wrap_app(self._get_linked_app_json())
        linked_app_v1.version = 100
        self._add_image_media(linked_app_v1)
        linked_app_v1.set_media_versions()
        self.assertEqual(linked_app_v1.multimedia_map['jr://file/commcare/case_list_image.jpg'].version, 100)

        linked_app_v2 = wrap_app(self._get_linked_app_json())
        linked_app_v2.version = 200
        previous_version_mock.return_value = linked_app_v1
        linked_app_v2.set_media_versions()

        self.assertFalse('jr://file/commcare/case_list_image.jpg' in linked_app_v2.multimedia_map)

        # set up updated app which would act like a revert to previous version
        linked_app_v3_doc = deepcopy(linked_app_v1.to_json())
        linked_app_v3_doc['version'] = 400
        linked_app_v3 = wrap_app(linked_app_v3_doc)
        previous_version_mock.return_value = linked_app_v2
        # re-set to mock a version in multimedia map received when taken from the master app
        linked_app_v3.multimedia_map['jr://file/commcare/case_list_image.jpg'].version = 300
        linked_app_v3.set_media_versions()

        # version NOT bumped to current version for media re-added in the revert but missing in previous version
        # by keeping the same version as in current multimedia map as pulled from master
        self.assertEqual(linked_app_v3.multimedia_map['jr://file/commcare/case_list_image.jpg'].version, 300)

        # ensure expected calls
        build_doc_mock.assert_not_called()
        wrap_app_mock.assert_not_called()
        self.assertEqual(previous_version_mock.call_count, 3)
