import inspect
import uuid
from io import BytesIO
from unittest.mock import Mock

import pytest
from couchdbkit import ResourceNotFound
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse
from PIL import Image

from corehq.apps.document_templates.images import get_image
from corehq.apps.document_templates.views import upload_area_image
from corehq.apps.hqmedia.models import CommCareImage

DOMAIN = 'document-templates-upload-test'


def _image(format='PNG'):
    """Image bytes that are unique, because hqmedia shares images with the same content"""
    buffer = BytesIO()
    Image.new('RGB', (10, 20), color=tuple(uuid.uuid4().bytes[:3])).save(buffer, format=format)
    return buffer.getvalue()


def _post(area='header', file=None, data=None):
    post = {**(data or {}), **({'image_file': file} if file else {})}
    request = RequestFactory().post('/', post)
    request.couch_user = Mock(username='user')
    return inspect.unwrap(upload_area_image)(request, DOMAIN, area)


def _delete_image(image_id):
    try:
        CommCareImage.get(image_id).delete()
    except ResourceNotFound:
        pass


def test_url_has_the_area():
    assert reverse('upload_document_template_image', args=[DOMAIN, 'header']).endswith('/templates/images/header/')


def test_unknown_area_is_not_found():
    with pytest.raises(Http404):
        _post(area='unknown', file=SimpleUploadedFile('a.png', _image()))


class TestUploadAreaImageView(TestCase):

    def test_stores_the_image_and_returns_the_area_fields(self):
        response = _post(file=SimpleUploadedFile('logo.png', _image()))
        content = response.content.decode()
        assert response.status_code == 200
        image_id = content.split('name="area_header_image" value="')[1].split('"')[0]
        self.addCleanup(_delete_image, image_id)
        assert DOMAIN in get_image(DOMAIN, image_id).valid_domains
        assert f'/{image_id}/?thumb=' in content
        assert 'is-invalid' not in content

    def test_rejected_image_keeps_the_current_one(self):
        response = _post(
            file=SimpleUploadedFile('logo.gif', _image('GIF')),
            data={'area_header_image': 'current-id'},
        )
        content = response.content.decode()
        assert 'Only PNG and JPEG' in content
        assert 'name="area_header_image" value="current-id"' in content

    def test_file_that_is_not_an_image_is_reported(self):
        content = _post(file=SimpleUploadedFile('logo.png', b'not an image')).content.decode()
        assert 'not a valid image' in content

    def test_missing_file_is_reported_and_leaves_no_thumbnail(self):
        content = _post().content.decode()
        assert 'Choose an image' in content
        assert '<img' not in content
