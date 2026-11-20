import uuid
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import ExifTags, Image

from corehq.apps.document_templates.images import (
    ImageError,
    _validate_and_orient_image,
    expire_unused_images,
    get_image,
    get_image_data,
    keep_images,
    load_images,
    save_image,
)
from corehq.apps.document_templates.models import Area
from corehq.blobs import CODES

from .utils import delete_image, make_image

DOMAIN = 'document-templates-images-test'
OTHER_DOMAIN = 'document-templates-images-other'


def _upload(data, name='logo.png'):
    return SimpleUploadedFile(name, data)


def _orientation(value):
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = value
    return exif


class TestSaveImage(SimpleTestCase):

    def test_no_file_is_rejected(self):
        with self.assertRaisesMessage(ImageError, 'Choose an image'):
            save_image(DOMAIN, None)

    @override_settings(MAX_UPLOAD_SIZE_ATTACHMENT=1024 * 1024)
    def test_large_file_is_rejected(self):
        upload = _upload(b'x' * (1024 * 1024 + 1))
        with self.assertRaisesMessage(ImageError, 'The limit is 1 MB'):
            save_image(DOMAIN, upload)


@pytest.mark.parametrize('format', ['PNG', 'JPEG'])
def test_image_without_orientation_is_kept_as_it_is(format):
    data = make_image(format)
    assert _validate_and_orient_image(data) == (data, format)


def test_image_with_upright_orientation_is_kept_as_it_is():
    data = make_image('JPEG', exif=_orientation(1))
    assert _validate_and_orient_image(data) == (data, 'JPEG')


@pytest.mark.parametrize('format', ['PNG', 'JPEG'])
def test_rotated_image_is_turned_upright(format):
    data, image_format = _validate_and_orient_image(make_image(format, size=(10, 20), exif=_orientation(6)))
    image = Image.open(BytesIO(data))
    assert (image_format, image.format, image.size) == (format, format, (20, 10))
    assert ExifTags.Base.Orientation not in image.getexif()


@pytest.mark.parametrize('data, message', [
    (make_image('GIF'), 'Only PNG, JPEG images can be used'),
    (b'not an image', 'not a valid image'),
    (make_image('PNG', size=(200, 200))[:-100], 'damaged'),
    (make_image('JPEG', size=(200, 200))[:-100], 'damaged'),
])
def test_unusable_image_is_rejected(data, message):
    with pytest.raises(ImageError, match=message):
        _validate_and_orient_image(data)


def test_image_with_too_many_pixels_is_rejected():
    with (
        patch('corehq.apps.document_templates.images.MAX_PIXELS', 199),
        pytest.raises(ImageError, match='too many pixels'),
    ):
        _validate_and_orient_image(make_image(size=(10, 20)))


class TestStoredImages(TestCase):

    def _save(self, domain=DOMAIN, data=None):
        key = save_image(domain, _upload(data or make_image()))
        self.addCleanup(delete_image, key)
        return key

    def test_saved_image_belongs_to_the_domain(self):
        meta = get_image(DOMAIN, self._save())
        assert (meta.domain, meta.parent_id, meta.type_code) == (DOMAIN, DOMAIN, CODES.document_template_image)
        assert (meta.name, meta.content_type) == ('logo.png', 'image/png')

    def test_saved_image_can_be_read_back(self):
        data = make_image()
        assert get_image_data(DOMAIN, self._save(data=data)) == data

    def test_same_image_uploaded_twice_is_stored_twice(self):
        data = make_image()
        assert self._save(data=data) != self._save(data=data)

    def test_image_of_another_domain_is_not_found(self):
        key = self._save(OTHER_DOMAIN)
        with self.assertRaisesMessage(ImageError, 'does not exist'):
            get_image(DOMAIN, key)

    def test_missing_image_is_reported(self):
        with self.assertRaisesMessage(ImageError, 'does not exist'):
            get_image(DOMAIN, uuid.uuid4().hex)

    def test_load_images_replaces_image_keys_with_bytes(self):
        data = make_image()
        markdown = Area(value='Hello')
        areas = {
            'header': Area(type='image', value=self._save(data=data)),
            'address': Area(type='image', value=''),
            'body': markdown,
        }
        loaded = load_images(DOMAIN, areas)
        assert loaded['header'] == Area(type='image', value=data)
        assert loaded['address'] == areas['address']
        assert loaded['body'] is markdown
        assert areas['header'].value != data  # the areas given are not changed

    def test_load_images_names_the_area_of_an_unusable_image(self):
        areas = {'header': Area(type='image', value=self._save())}
        with self.assertRaisesMessage(ImageError, 'header: The image does not exist.'):
            load_images(OTHER_DOMAIN, areas)


class TestImageExpiry(TestCase):

    def _save(self, domain=DOMAIN):
        key = save_image(domain, _upload(make_image()))
        self.addCleanup(delete_image, key)
        return key

    @staticmethod
    def _expires_on(key, domain=DOMAIN):
        return get_image(domain, key).expires_on

    def test_upload_expires_in_a_day(self):
        expires_on = self._expires_on(self._save())
        assert datetime.utcnow() + timedelta(hours=23) < expires_on < datetime.utcnow() + timedelta(hours=25)

    def test_kept_images_do_not_expire(self):
        header, footer = self._save(), self._save()
        keep_images(DOMAIN, {
            'header': Area(type='image', value=header),
            'body': Area(value=footer),  # markdown that looks like a key is not an image
        })
        assert self._expires_on(header) is None
        assert self._expires_on(footer) is not None

    def test_keep_images_ignores_images_of_another_domain(self):
        key = self._save(OTHER_DOMAIN)
        keep_images(DOMAIN, {'header': Area(type='image', value=key)})
        assert self._expires_on(key, OTHER_DOMAIN) is not None

    def test_images_no_longer_used_expire(self):
        kept, dropped = self._save(), self._save()
        old_areas = {'header': Area(type='image', value=kept), 'footer': Area(type='image', value=dropped)}
        keep_images(DOMAIN, old_areas)
        expire_unused_images(DOMAIN, old_areas, {**old_areas, 'footer': Area(value='Bye')})
        assert self._expires_on(kept) is None
        assert self._expires_on(dropped) < datetime.utcnow() + timedelta(hours=2)

    def test_expire_unused_images_of_a_new_template(self):
        expire_unused_images(DOMAIN, None, {'header': Area(type='image', value=self._save())})
