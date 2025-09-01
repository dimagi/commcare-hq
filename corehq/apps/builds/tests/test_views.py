import json
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch


class TestImportBuildView(TestCase):

    def setUp(self):
        self.url = reverse('import_build')

    def test_import_build_invalid_version(self):
        with patch('corehq.apps.builds.views.CommCareBuild.create_without_artifacts') as mock_create:
            response = self.client.post(self.url, {'version': '1.2.dev'})

            assert response.status_code == 400
            response_json = json.loads(response.content)
            assert response_json['reason'] == 'Badly formatted version'
            mock_create.assert_not_called()

    def test_import_build_valid_version(self):
        with patch('corehq.apps.builds.views.CommCareBuild.create_without_artifacts') as mock_create:
            mock_build = mock_create.return_value
            mock_build.get_id = 'test_build_id_123'

            response = self.client.post(self.url, {'version': '1.2.3'})

            assert response.status_code == 200
            response_json = json.loads(response.content)
            assert response_json['message'] == 'New CommCare build added'
            mock_create.assert_called_once_with('1.2.3', None)
