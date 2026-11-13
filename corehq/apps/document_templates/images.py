import attrs
from couchdbkit import ResourceNotFound
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _

from corehq.apps.document_templates.models import IMAGE
from corehq.apps.hqmedia.exceptions import BadMediaFileException
from corehq.apps.hqmedia.models import CommCareImage

ALLOWED_FORMATS = ('PNG', 'JPEG')
THUMBNAIL_PIXELS = 120


class ImageError(Exception):
    """An image that cannot be used. The message is meant for the user"""


def save_image(domain, uploaded_file, username):
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
        CommCareImage.get_image_object(data, formats=ALLOWED_FORMATS)
    except BadMediaFileException as err:
        raise ImageError(str(err))


def get_image(domain, image_id):
    try:
        return CommCareImage.get_for_domain(domain, image_id)
    except ResourceNotFound:
        raise ImageError(_('The image does not exist.'))


def get_image_data(domain, image_id):
    """:returns: the bytes of the image with ``image_id``"""
    data = get_image(domain, image_id).get_display_file(return_type=False)
    if not data:
        raise ImageError(_('The image does not exist.'))
    return data


def load_images(domain, areas):
    """:returns: ``areas`` (``{name: Area}``) with the id of each image area replaced by the bytes of the image
    :raises ImageError: if an image cannot be used; the message names the area
    """
    loaded = {}
    for name, area in areas.items():
        if area.type == IMAGE and area.value:
            try:
                area = attrs.evolve(area, value=get_image_data(domain, area.value))
            except ImageError as error:
                raise ImageError(f'{name}: {error}')
        loaded[name] = area
    return loaded


def get_thumbnail_url(image_id):
    return reverse('hqmedia_download', args=['CommCareImage', image_id]) + f'?thumb={THUMBNAIL_PIXELS}'
