import uuid
from io import BytesIO

import pytest
from couchdbkit import ResourceNotFound
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from corehq.apps.document_templates.images import (
    MAX_PIXELS,
    ImageError,
    _check_image,
    get_image,
    get_image_data,
    save_image,
)
from corehq.apps.hqmedia.models import CommCareImage

DOMAIN = 'document-templates-images-test'
OTHER_DOMAIN = 'document-templates-images-other'


def _image(format='PNG', size=(10, 20)):
    """Image bytes that are unique, because hqmedia shares images with the same content"""
    image = Image.new('RGB', size, color=tuple(uuid.uuid4().bytes[:3]))
    buffer = BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


def _delete_image(image_id):
    try:
        CommCareImage.get(image_id).delete()
    except ResourceNotFound:
        pass  # saved twice, deleted already


def _upload(data, name='logo.png'):
    return SimpleUploadedFile(name, data)


@pytest.mark.parametrize('format', ['PNG', 'JPEG'])
def test_allowed_formats_are_accepted(format):
    _check_image(_image(format))


@pytest.mark.parametrize('format', ['GIF', 'WEBP', 'BMP', 'TIFF'])
def test_other_formats_are_rejected(format):
    with pytest.raises(ImageError, match='Only PNG and JPEG'):
        _check_image(_image(format))


def test_a_file_that_is_not_an_image_is_rejected():
    with pytest.raises(ImageError, match='not a valid image'):
        _check_image(b'%PDF-1.4 not an image')


@pytest.mark.parametrize('size, rejected', [
    ((MAX_PIXELS, MAX_PIXELS), False),
    ((MAX_PIXELS + 1, 10), True),
    ((10, MAX_PIXELS + 1), True),
])
def test_image_size_is_limited(size, rejected):
    data = _image(size=size)
    if rejected:
        with pytest.raises(ImageError, match='4000 x 4000 pixels'):
            _check_image(data)
    else:
        _check_image(data)


class TestSaveImage(SimpleTestCase):

    def test_no_file_is_rejected(self):
        with self.assertRaisesMessage(ImageError, 'Choose an image'):
            save_image(DOMAIN, None, 'user')

    @override_settings(MAX_UPLOAD_SIZE_ATTACHMENT=1024 * 1024)
    def test_large_file_is_rejected(self):
        upload = _upload(b'x' * (1024 * 1024 + 1))
        with self.assertRaisesMessage(ImageError, 'The limit is 1 MB'):
            save_image(DOMAIN, upload, 'user')


class TestImagesInHqmedia(TestCase):

    def _save(self, domain=DOMAIN, data=None):
        image_id = save_image(domain, _upload(data or _image()), 'user')
        self.addCleanup(_delete_image, image_id)
        return image_id

    def test_saved_image_is_owned_by_the_domain(self):
        image = get_image(DOMAIN, self._save())
        assert DOMAIN in image.valid_domains
        assert DOMAIN in image.owners

    def test_saved_image_can_be_read_back(self):
        data = _image()
        image_id = self._save(data=data)
        assert get_image_data(DOMAIN, image_id) == data

    def test_domain_that_does_not_own_the_image_cannot_use_it(self):
        image_id = self._save()
        with self.assertRaisesMessage(ImageError, 'does not belong to this project'):
            get_image(OTHER_DOMAIN, image_id)
        with self.assertRaisesMessage(ImageError, 'does not belong to this project'):
            get_image_data(OTHER_DOMAIN, image_id)

    def test_same_image_uploaded_by_two_domains_is_owned_by_both(self):
        data = _image()
        image_id = self._save(DOMAIN, data)
        assert self._save(OTHER_DOMAIN, data) == image_id
        get_image(DOMAIN, image_id)
        get_image(OTHER_DOMAIN, image_id)

    def test_missing_image_is_reported(self):
        with self.assertRaisesMessage(ImageError, 'does not exist'):
            get_image(DOMAIN, uuid.uuid4().hex)
