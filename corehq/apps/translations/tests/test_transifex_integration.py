from django.test import SimpleTestCase

import requests_mock

from corehq.apps.translations.integrations.transifex.client import (
    TransifexApiClient,
)
from corehq.util.test_utils import TestFileMixin

TOKEN = "1234"
ORGANIZATION_SLUG = "test-organization"
PROJECT_SLUG = "test-project"
RESOURCE_SLUG = "test-resource"

DATA_PATH = 'corehq/apps/translations/tests/data/transifex_api/'


class TestTransifexApiClient(TestFileMixin, SimpleTestCase):

    @classmethod
    @requests_mock.Mocker()
    def setUpClass(cls, mocker):
        super().setUpClass()
        cls.mocker = mocker
        cls.mocker.register_uri(requests_mock.ANY, requests_mock.ANY, json=cls._route_request)
        cls.tfx_client = TransifexApiClient(TOKEN, ORGANIZATION_SLUG, PROJECT_SLUG)

    def tearDown(self):
        super().tearDown()
        self.mocker.reset_mock()

    @classmethod
    def _route_request(cls, request, context):
        if request.method == 'DELETE':
            context.status_code = 204
            return
        if request.method == 'GET' and 'downloads/' in request.path:
            return cls._handle_download_redirect(request, context)
        return cls._get_json(request)

    @classmethod
    def _handle_download_redirect(cls, request, context):
        if request.path.endswith('content'):
            return cls._get_json(request)

        # Set redirect to our predefined content irrespective of ID
        url_pieces = request.url.split('/')
        url_pieces[-1] = 'content'
        context.status_code = 303
        context.headers['location'] = '/'.join(url_pieces)
        return

    @classmethod
    def _get_json(cls, request):
        path_text = request.path.replace('/', '_')
        file_path = DATA_PATH + request.method.lower() + path_text
        return cls.get_json(file_path)

    def test_auth_setup(self):
        expected_headers = {'Authorization': 'Bearer ' + TOKEN}
        self.assertEqual(self.tfx_client.api.make_auth_headers(), expected_headers)

    def test_get_object_by_slug(self):
        cls = self.tfx_client.api.Resource
        key = 'slug'
        value = RESOURCE_SLUG
        with self.mocker as mocker:
            self.tfx_client._get_object(cls, **{key: value})
            request = mocker.last_request

        expected_filter = f"filter[{key}]"
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.qs[expected_filter], [value])

    def test_list_objects(self):
        cls = self.tfx_client.api.Resource
        key = 'project'
        value = self.tfx_client.project.id
        with self.mocker as mocker:
            self.tfx_client._list_objects(cls, **{key: value}).get()
            request = mocker.last_request

        expected_filter = f"filter[{key}]"
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.qs[expected_filter], [value])

    def test_create_resource(self):
        resource_name = "Test Resource"
        with self.mocker as mocker:
            self.tfx_client._create_resource(RESOURCE_SLUG, resource_name)
            request = mocker.last_request

        data = request.json()['data']
        self.assertEqual(request.method, 'POST')
        self.assertEqual(data['attributes']['slug'], RESOURCE_SLUG)
        self.assertEqual(data['attributes']['name'], resource_name)

    def test_delete_resource(self):
        with self.mocker as mocker:
            resource = self.tfx_client._get_resource(RESOURCE_SLUG)
            self.tfx_client.delete_resource(RESOURCE_SLUG)
            request = mocker.last_request

        self.assertEqual(request.method, 'DELETE')
        self.assertTrue(request.path.endswith(resource.id))

    def test_upload_content_for_resource(self):
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

    def test_download_content_for_resource(self):
        cls = self.tfx_client.api.ResourceStringsAsyncDownload
        key = 'resource'
        with self.mocker as mocker:
            value = self.tfx_client._get_resource(RESOURCE_SLUG).id
            content = self.tfx_client._download_content(cls, **{key: value})
            post_download, get_download_status, get_content = mocker.request_history[-3:]

        # creates async download request
        data = post_download.json()['data']
        self.assertEqual(post_download.method, 'POST')
        self.assertEqual(data['attributes'][key], value)

        # checks status of download
        self.assertEqual(get_download_status.method, 'GET')

        # returns expected content
        expected_content = self.get_file(DATA_PATH + '/get_resource_strings_async_downloads_content', 'json')
        self.assertEqual(get_content.method, 'GET')
        self.assertEqual(content.decode('utf-8'), expected_content)
