from django.test import SimpleTestCase

import requests_mock

from corehq.apps.translations.integrations.transifex.client import (
    TransifexApiClient,
)
from corehq.util.test_utils import TestFileMixin

TOKEN = "1234"
ORGANIZATION_SLUG = "test-organization"
PROJECT_SLUG = "test-project"

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
        return cls._get_json(request)

    @classmethod
    def _get_json(cls, request):
        path_text = request.path.replace('/', '_')
        file_path = DATA_PATH + request.method.lower() + path_text
        return cls.get_json(file_path)

    def test_auth_setup(self):
        expected_headers = {'Authorization': 'Bearer ' + TOKEN}
        self.assertEqual(self.tfx_client.api.make_auth_headers(), expected_headers)

    def test_get_object_by_slug(self):
        ...

    def test_list_objects(self):
        ...

    def test_create_resource(self):
        ...

    def test_delete_resource(self):
        ...

    def test_upload_content_for_resource(self):
        ...

    def test_download_content_for_resource(self):
        ...
