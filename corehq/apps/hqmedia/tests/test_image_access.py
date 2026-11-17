from io import BytesIO

import pytest
from couchdbkit import ResourceNotFound
from django.test import TestCase
from PIL import Image

from corehq.apps.hqmedia.exceptions import BadMediaFileException
from corehq.apps.hqmedia.models import CommCareImage


class TestGetForDomain(TestCase):

    def setUp(self):
        self.image = CommCareImage(valid_domains=['mine'])
        self.image.save()
        self.addCleanup(self.image.delete)

    def test_domain_with_access(self):
        assert CommCareImage.get_for_domain('mine', self.image._id)._id == self.image._id

    def test_other_domain(self):
        with pytest.raises(ResourceNotFound):
            CommCareImage.get_for_domain('theirs', self.image._id)

    def test_missing_id(self):
        with pytest.raises(ResourceNotFound):
            CommCareImage.get_for_domain('mine', 'does-not-exist')


def _image_bytes(format):
    buffer = BytesIO()
    Image.new('RGB', (2, 2)).save(buffer, format=format)
    return buffer.getvalue()


@pytest.mark.parametrize('format, formats, rejected', [
    ('PNG', ('PNG', 'JPEG'), False),
    ('JPEG', ('PNG', 'JPEG'), False),
    ('GIF', ('PNG', 'JPEG'), True),
    ('GIF', None, False),
])
def test_get_image_object_formats(format, formats, rejected):
    data = _image_bytes(format)
    if rejected:
        with pytest.raises(BadMediaFileException, match='Only PNG, JPEG'):
            CommCareImage.get_image_object(data, formats=formats)
    else:
        assert CommCareImage.get_image_object(data, formats=formats).format == format


def test_get_image_object_rejects_non_image():
    with pytest.raises(BadMediaFileException, match='not a valid image'):
        CommCareImage.get_image_object(b'not an image')
