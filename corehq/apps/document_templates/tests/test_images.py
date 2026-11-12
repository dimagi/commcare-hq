import uuid
from io import BytesIO

from couchdbkit import ResourceNotFound
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from corehq.apps.document_templates.images import (
    ImageError,
    get_image,
    get_image_data,
    save_image,
)
from corehq.apps.hqmedia.models import CommCareImage

DOMAIN = 'document-templates-images-test'
OTHER_DOMAIN = 'document-templates-images-other'


def _image(format='PNG'):
    image = Image.new('RGB', (10, 20), color=tuple(uuid.uuid4().bytes[:3]))
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

    def test_same_image_uploaded_by_two_domains_is_owned_by_both(self):
        data = _image()
        image_id = self._save(DOMAIN, data)
        assert self._save(OTHER_DOMAIN, data) == image_id
        get_image(DOMAIN, image_id)
        get_image(OTHER_DOMAIN, image_id)

    def test_missing_image_is_reported(self):
        with self.assertRaisesMessage(ImageError, 'does not exist'):
            get_image(DOMAIN, uuid.uuid4().hex)
