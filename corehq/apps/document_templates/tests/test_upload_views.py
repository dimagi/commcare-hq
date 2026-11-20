import inspect
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, TestCase

from corehq.apps.document_templates.images import get_image_data, get_image_url, save_image
from corehq.apps.document_templates.views import download_area_image, upload_area_image

from .utils import delete_image, make_image

DOMAIN = 'document-templates-upload-test'


def _post(area='header', file=None, data=None):
    post = {**(data or {}), **({'image_file': file} if file else {})}
    request = RequestFactory().post('/', post)
    request.couch_user = Mock(username='user')
    return inspect.unwrap(upload_area_image)(request, DOMAIN, area)


class TestUploadAreaImageView(TestCase):

    def test_unknown_area_is_not_found(self):
        with pytest.raises(Http404):
            _post(area='unknown', file=SimpleUploadedFile('a.png', make_image()))

    def test_stores_the_image_and_returns_the_area_fields(self):
        response = _post(file=SimpleUploadedFile('logo.png', make_image()))
        content = response.content.decode()
        assert response.status_code == 200
        key = content.split('name="area_header_image" value="')[1].split('"')[0]
        self.addCleanup(delete_image, key)
        assert get_image_data(DOMAIN, key)
        assert f'src="{get_image_url(DOMAIN, key)}"' in content
        assert 'is-invalid' not in content

    def test_rejected_image_keeps_the_current_one(self):
        response = _post(
            file=SimpleUploadedFile('logo.gif', make_image('GIF')),
            data={'area_header_image': 'current-id'},
        )
        content = response.content.decode()
        assert 'Only PNG, JPEG images can be used' in content
        assert 'name="area_header_image" value="current-id"' in content

    def test_file_that_is_not_an_image_is_reported(self):
        content = _post(file=SimpleUploadedFile('logo.png', b'not an image')).content.decode()
        assert 'not a valid image' in content

    def test_missing_file_is_reported_and_leaves_no_thumbnail(self):
        content = _post().content.decode()
        assert 'Choose an image' in content
        assert '<img' not in content


class TestDownloadAreaImageView(TestCase):

    def _get(self, domain, key):
        return inspect.unwrap(download_area_image)(RequestFactory().get('/'), domain, key)

    def _save(self, domain, data):
        key = save_image(domain, SimpleUploadedFile('logo.png', data))
        self.addCleanup(delete_image, key)
        return key

    def test_returns_the_image(self):
        data = make_image()
        response = self._get(DOMAIN, self._save(DOMAIN, data))
        assert response.content == data
        assert response['Content-Type'] == 'image/png'
        assert response['X-Content-Type-Options'] == 'nosniff'

    def test_image_of_another_domain_is_not_found(self):
        key = self._save('document-templates-upload-other', make_image())
        with pytest.raises(Http404):
            self._get(DOMAIN, key)

    def test_missing_image_is_not_found(self):
        with pytest.raises(Http404):
            self._get(DOMAIN, 'does-not-exist')
