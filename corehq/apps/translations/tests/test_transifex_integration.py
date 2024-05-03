from django.test import SimpleTestCase

import polib
import requests_mock
from unittest.mock import patch

from corehq.apps.translations.integrations.transifex.client import TransifexApiClient
from corehq.util.test_utils import TestFileMixin

TOKEN = "1234"
ORGANIZATION_SLUG = "test-organization"
PROJECT_SLUG = "test-project"
RESOURCE_SLUG = "test-resource"
RESOURCE_NAME = "Test Resource"

DATA_PATH = 'corehq/apps/translations/tests/data/transifex/'


class TestTransifexApiClient(TestFileMixin, SimpleTestCase):

    @classmethod
    @requests_mock.Mocker()
    def setUpClass(cls, mocker):
        super().setUpClass()
        cls.mocker = mocker
        cls.mocker.register_uri(requests_mock.ANY, requests_mock.ANY, text=cls.route_request)
        cls.tfx_client = TransifexApiClient(TOKEN, ORGANIZATION_SLUG, PROJECT_SLUG)

    def tearDown(self):
        super().tearDown()
        self.mocker.reset_mock()

    @classmethod
    def route_request(cls, request, context):
        if request.method == 'DELETE':
            context.status_code = 204
            return
        if request.method == 'GET' and 'downloads/' in request.path:
            return cls._handle_download_redirect(request, context)
        return cls._get_file(request, 'json')

    @classmethod
    def _handle_download_redirect(cls, request, context):
        if request.path.endswith('content'):
            return cls._get_file(request, 'txt')

        # Set redirect to our predefined content irrespective of ID
        url_pieces = request.url.split('/')
        url_pieces[-1] = 'content'
        context.status_code = 303
        context.headers['location'] = '/'.join(url_pieces)
        return

    @classmethod
    def _get_file(cls, request, ext):
        path_text = request.path.replace('/', '_')
        file_path = DATA_PATH + 'api/' + request.method.lower() + path_text
        return cls.get_file(file_path, ext)

    def test_auth_setup(self):
        expected_headers = {'Authorization': 'Bearer ' + TOKEN}
        self.assertEqual(self.tfx_client.api.make_auth_headers(), expected_headers)

    def test_request_get_object_by_slug(self):
        cls = self.tfx_client.api.Resource
        key = 'slug'
        value = RESOURCE_SLUG
        with self.mocker as mocker:
            obj = self.tfx_client._get_object(cls, **{key: value})
            request = mocker.last_request

        expected_filter = f"filter[{key}]"
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.qs[expected_filter], [value])
        self.assertIsInstance(obj, cls)

    def test_request_list_objects(self):
        cls = self.tfx_client.api.Resource
        key = 'project'
        value = self.tfx_client.project.id
        with self.mocker as mocker:
            objects = [o for o in self.tfx_client._list_objects(cls, **{key: value})]
            request = mocker.last_request

        expected_filter = f"filter[{key}]"
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.qs[expected_filter], [value])
        self.assertIsInstance(objects[0], cls)

    def test_request_fetch_related(self):
        obj = self.tfx_client.project
        relative = 'languages'
        with self.mocker as mocker:
            [r for r in self.tfx_client._fetch_related(obj, 'languages')]
            request = mocker.last_request

        self.assertEqual(request.method, 'GET')
        self.assertIn(obj.id, request.path)
        self.assertIn(relative, request.path)

    def test_request_create_resource(self):
        with self.mocker as mocker:
            self.tfx_client._create_resource(RESOURCE_SLUG, RESOURCE_NAME)
            request = mocker.last_request

        data = request.json()['data']
        self.assertEqual(request.method, 'POST')
        self.assertEqual(data['attributes']['slug'], RESOURCE_SLUG)
        self.assertEqual(data['attributes']['name'], RESOURCE_NAME)

    def test_request_lock_resource(self):
        with self.mocker as mocker:
            resource = self.tfx_client._get_resource(RESOURCE_SLUG)
            self.tfx_client._lock_resource(resource)
            request = mocker.last_request

        data = request.json()['data']
        self.assertEqual(request.method, 'PATCH')
        self.assertEqual(data['id'], resource.id)
        self.assertEqual(data['attributes']['accept_translations'], False)

    def test_request_delete_resource(self):
        with self.mocker as mocker:
            resource = self.tfx_client._get_resource(RESOURCE_SLUG)
            self.tfx_client.delete_resource(RESOURCE_SLUG)
            request = mocker.last_request

        self.assertEqual(request.method, 'DELETE')
        self.assertTrue(request.path.endswith(resource.id))

    def test_request_upload_content_for_resource(self):
        cls = self.tfx_client.api.ResourceStringsAsyncUpload
        content = "Here is some content"
        key = 'resource'
        with self.mocker as mocker:
            value = self.tfx_client._get_resource(RESOURCE_SLUG).id
            self.tfx_client._upload_content(cls, content, **{key: value})
            request = mocker.last_request

        text = request.text
        self.assertEqual(request.method, 'POST')
        self.assertIn(content, text)
        self.assertIn(key, text)
        self.assertIn(value, text)

    def test_request_download_content_for_resource(self):
        cls = self.tfx_client.api.ResourceStringsAsyncDownload
        key = 'resource'
        with self.mocker as mocker:
            value = self.tfx_client._get_resource(RESOURCE_SLUG).id
            self.tfx_client._download_content(cls, **{key: value})
            # with our mocked redirect, Transifex async downloads should make exactly 3 requests
            post_download, get_download_status, get_content = mocker.request_history[-3:]

        # creates async download request
        data = post_download.json()['data']
        self.assertEqual(post_download.method, 'POST')
        self.assertEqual(data['attributes'][key], value)

        # checks status of download
        self.assertEqual(get_download_status.method, 'GET')

        # finally, gets content from download
        self.assertEqual(get_content.method, 'GET')

    @patch('corehq.apps.translations.integrations.transifex.client.TransifexApiClient._upload_resource_strings')
    @patch('corehq.apps.translations.integrations.transifex.client.TransifexApiClient._get_resource')
    @patch('corehq.apps.translations.integrations.transifex.client.TransifexApiClient._create_resource')
    def test_upload_resource(self, create_resource, get_resource, upload_resource_strings):
        filename = 'menus_and_forms.po'
        path = DATA_PATH + filename
        with self.mocker:
            self.tfx_client.upload_resource(path, RESOURCE_SLUG, RESOURCE_NAME, False)

        content = self.get_file(path, '')
        resource = create_resource.return_value
        create_resource.assert_called_with(RESOURCE_SLUG, RESOURCE_NAME)
        upload_resource_strings.assert_called_with(content, resource.id)

        # with update_resource True we should get the existing resource instead of creating
        with self.mocker:
            self.tfx_client.upload_resource(path, RESOURCE_SLUG, RESOURCE_NAME, True)
        get_resource.assert_called_with(RESOURCE_SLUG)

        # with resource_name None we should create the resource using its filename as resource_name
        with self.mocker:
            self.tfx_client.upload_resource(path, RESOURCE_SLUG, None, False)
        create_resource.assert_called_with(RESOURCE_SLUG, filename)

    @patch(
        'corehq.apps.translations.integrations.transifex.client.TransifexApiClient._upload_resource_translations')
    @patch('corehq.apps.translations.integrations.transifex.client.TransifexApiClient._get_resource')
    def test_upload_translation(self, get_resource, upload_resource_translations):
        path = DATA_PATH + 'menus_and_forms-fr.po'
        hq_lang_code = 'fra'
        with self.mocker:
            self.tfx_client.upload_translation(path, RESOURCE_SLUG, hq_lang_code)

        content = self.get_file(path, '')
        resource = get_resource.return_value
        language_id = self.tfx_client._to_language_id(self.tfx_client.transifex_lang_code(hq_lang_code))
        upload_resource_translations.assert_called_with(content, resource.id, language_id)

    @patch('corehq.apps.translations.integrations.transifex.client.TransifexApiClient._list_resources')
    def test_get_resource_slugs(self, list_resources):
        all_slugs = ['test-resource', 'test-resourcev2', 'test-resourcev3']
        all_resources = [self.tfx_client.api.Resource(slug=slug) for slug in all_slugs]
        list_resources.return_value = all_resources

        # no version arg returns all slugs
        actual_slugs = self.tfx_client.get_resource_slugs(None)
        self.assertEqual(all_slugs, actual_slugs)

        # version arg with "use_version_postfix" returns matching that version
        actual_slugs = self.tfx_client.get_resource_slugs(2)
        self.assertEqual(['test-resourcev2'], actual_slugs)

        # version arg without "use_version_postfix" returns those not matching the version
        self.tfx_client.use_version_postfix = False
        actual_slugs = self.tfx_client.get_resource_slugs(2)
        self.assertEqual(['test-resource', 'test-resourcev3'], actual_slugs)

    def test_get_translation(self):
        hq_lang_code = 'fra'
        with self.mocker:
            actual_translation = self.tfx_client.get_translation(RESOURCE_SLUG, hq_lang_code, False)

        path = DATA_PATH + 'menus_and_forms-fr.po'
        expected_translation = polib.pofile(self.get_file(path, ''))
        self.assertEqual(expected_translation, actual_translation)

    def test_get_project_langcodes(self):
        expected_langcodes = ['es', 'fr', 'en']
        with self.mocker:
            actual_langcodes = self.tfx_client.get_project_langcodes()

        self.assertEqual(expected_langcodes, actual_langcodes)

    def test_source_lang_is(self):
        transifex_language_id = 'l:fr'
        hq_lang_code = 'fra'
        self.tfx_client.project.source_language.id = transifex_language_id
        self.assertTrue(self.tfx_client.source_lang_is(hq_lang_code))

    def test_is_translation_completed(self):
        with self.mocker:
            # some translations are incomplete in our test data
            translation_completed = self.tfx_client.is_translation_completed(RESOURCE_SLUG)
        self.assertFalse(translation_completed)

        with self.mocker:
            # translations for French ('fra') are complete in our test data
            hq_lang_code = 'fra'
            translation_completed = self.tfx_client.is_translation_completed(
                RESOURCE_SLUG, hq_lang_code=hq_lang_code)
        self.assertTrue(translation_completed)
