import inspect
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, TestCase

from corehq.apps.document_templates.images import get_image
from corehq.apps.document_templates.views import upload_area_image

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
        image_id = content.split('name="area_header_image" value="')[1].split('"')[0]
        self.addCleanup(delete_image, image_id)
        assert DOMAIN in get_image(DOMAIN, image_id).valid_domains
        assert f'/{image_id}/?thumb=' in content
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
