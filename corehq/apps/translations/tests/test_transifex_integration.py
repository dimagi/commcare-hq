from django.test import SimpleTestCase

import requests_mock

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
        return cls._get_file(request, 'json')

    @classmethod
    def _get_file(cls, request, ext):
        path_text = request.path.replace('/', '_')
        file_path = DATA_PATH + 'api/' + request.method.lower() + path_text
        return cls.get_file(file_path, ext)

    def test_auth_setup(self):
        expected_headers = {'Authorization': 'Bearer ' + TOKEN}
        self.assertEqual(self.tfx_client.api.make_auth_headers(), expected_headers)

    def test_request_get_object_by_slug(self):
        ...

    def test_request_list_objects(self):
        ...

    def test_request_fetch_related(self):
        ...

    def test_request_create_resource(self):
        ...

    def test_request_lock_resource(self):
        ...

    def test_request_delete_resource(self):
        ...

    def test_request_upload_content_for_resource(self):
        ...

    def test_request_download_content_for_resource(self):
        ...
