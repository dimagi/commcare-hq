"""
Stores the images of document template areas in hqmedia.

An area of type ``image`` holds the id of a ``CommCareImage``. hqmedia shares
images between projects by their hash, so an id alone says nothing about who
may use the image: :func:`get_image_data` only returns images the project
owns, and :func:`save_image` is the way to become an owner.
"""
from io import BytesIO

from couchdbkit import ResourceNotFound
from django.conf import settings
from django.utils.translation import gettext as _
from PIL import Image

from corehq.apps.hqmedia.models import CommCareImage

ALLOWED_FORMATS = ('PNG', 'JPEG')
MAX_PIXELS = 4000  # width and height; reportlab decodes the image when it renders the PDF


class ImageError(Exception):
    """An image that cannot be used. The message is meant for the user"""


def save_image(domain, uploaded_file, username):
    """Store an uploaded image in hqmedia for ``domain``

    :returns: the id of the ``CommCareImage``
    """
    if not uploaded_file:
        raise ImageError(_('Choose an image to upload.'))
    if uploaded_file.size > settings.MAX_UPLOAD_SIZE_ATTACHMENT:
        raise ImageError(_('The image is too large. The limit is {size} MB.').format(
            size=settings.MAX_UPLOAD_SIZE_ATTACHMENT // (1024 * 1024),
        ))
    data = uploaded_file.read()
    _check_image(data)

    image = CommCareImage.get_by_data(data)
    image.attach_data(data, original_filename=uploaded_file.name, username=username)
    image.add_domain(domain, owner=True)
    return image._id


def _check_image(data):
    try:
        image = Image.open(BytesIO(data))
    except (OSError, Image.DecompressionBombError):
        raise ImageError(_('The file is not a valid image.'))
    if image.format not in ALLOWED_FORMATS:
        raise ImageError(_('Only PNG and JPEG images can be used.'))
    if max(image.size) > MAX_PIXELS:
        raise ImageError(_('The image is too large. The limit is {pixels} x {pixels} pixels.').format(
            pixels=MAX_PIXELS,
        ))


def get_image(domain, image_id):
    """:returns: the ``CommCareImage`` with ``image_id`` if ``domain`` owns it"""
    try:
        image = CommCareImage.get(image_id)
    except ResourceNotFound:
        raise ImageError(_('The image does not exist.'))
    if domain not in image.valid_domains:
        raise ImageError(_('The image does not belong to this project.'))
    return image


def get_image_data(domain, image_id):
    """:returns: the bytes of the image with ``image_id``"""
    data = get_image(domain, image_id).get_display_file(return_type=False)
    if not data:
        raise ImageError(_('The image does not exist.'))
    return data
