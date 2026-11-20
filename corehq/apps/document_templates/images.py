from io import BytesIO
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _
from PIL import ExifTags, Image, ImageOps

from corehq.apps.document_templates.models import IMAGE
from corehq.apps.document_templates.rendering import DocumentRenderError, ImageContent
from corehq.blobs import CODES, NotFound, get_blob_db
from corehq.blobs.models import BlobMeta

ALLOWED_FORMATS = ('PNG', 'JPEG')
MAX_PIXELS = 25_000_000
JPEG_QUALITY = 95
UPLOAD_LIFETIME_MINUTES = 24 * 60  # until a template that uses the image is saved


class ImageError(Exception):
    """An image that cannot be used. The message is meant for the user"""


def save_image(domain, uploaded_file):
    """:returns: the key of the stored image"""
    if not uploaded_file:
        raise ImageError(_('Choose an image to upload.'))
    if uploaded_file.size > settings.MAX_UPLOAD_SIZE_ATTACHMENT:
        raise ImageError(_('The image is too large. The limit is {size} MB.').format(
            size=settings.MAX_UPLOAD_SIZE_ATTACHMENT // (1024 * 1024),
        ))
    data, image_format = _validate_and_orient_image(uploaded_file.read())
    meta = get_blob_db().put(
        BytesIO(data),
        domain=domain,
        parent_id=domain,
        type_code=CODES.document_template_image,
        name=uploaded_file.name,
        content_type=Image.MIME[image_format],
        timeout=UPLOAD_LIFETIME_MINUTES,
    )
    return meta.key


def keep_images(domain, areas):
    """Stop the images of ``areas`` from expiring; call before saving a template with ``areas``"""
    keys = _image_keys(areas)
    if keys:
        BlobMeta.objects.partitioned_query(domain).filter(
            parent_id=domain,
            type_code=CODES.document_template_image,
            key__in=keys,
        ).update(expires_on=None)


def expire_unused_images(domain, old_areas, new_areas):
    """Expire the images of ``old_areas`` that ``new_areas`` no longer use; call after saving a template"""
    db = get_blob_db()
    for key in _image_keys(old_areas) - _image_keys(new_areas):
        db.expire(domain, key)


def _image_keys(areas):
    return {area.value for area in (areas or {}).values() if area.type == IMAGE and area.value}


def _validate_and_orient_image(data):
    """Check that ``data`` is a usable image

    :returns: ``(data, format)``; ``data`` is re-encoded, without its EXIF data, only if the EXIF
        orientation says it has to be rotated or flipped to be shown upright
    """
    try:
        image = Image.open(BytesIO(data))
    except (OSError, Image.DecompressionBombError):
        raise ImageError(_('Upload is not a valid image file.'))
    if image.format not in ALLOWED_FORMATS:
        raise ImageError(_('Only {formats} images can be used.').format(formats=', '.join(ALLOWED_FORMATS)))
    if image.width * image.height > MAX_PIXELS:
        raise ImageError(_('The image has too many pixels. The limit is {limit} million.').format(
            limit=MAX_PIXELS // 1_000_000,
        ))
    image_format = image.format
    try:
        image.load()
    except (OSError, SyntaxError, ValueError):
        raise ImageError(_('The image file is damaged.'))
    if image.getexif().get(ExifTags.Base.Orientation, 1) == 1:
        return data, image_format
    buffer = BytesIO()
    options = {'quality': JPEG_QUALITY} if image_format == 'JPEG' else {}
    ImageOps.exif_transpose(image).save(buffer, format=image_format, **options)
    return buffer.getvalue(), image_format


def get_image(domain, key):
    """:returns: the ``BlobMeta`` of the image of ``domain`` with ``key``"""
    try:
        return BlobMeta.objects.partitioned_query(domain).get(
            parent_id=domain,
            type_code=CODES.document_template_image,
            key=key,
        )
    except BlobMeta.DoesNotExist:
        raise ImageError(_('The image does not exist.'))


def get_image_data(domain, key):
    """:returns: the bytes of the image of ``domain`` with ``key``"""
    return read_image(get_image(domain, key))


def read_image(meta):
    """:returns: the bytes of the image with ``meta``"""
    try:
        with get_blob_db().get(meta=meta) as blob:
            return blob.read()
    except NotFound:
        raise ImageError(_('The image does not exist.'))


def load_images(domain, areas):
    """:returns: ``areas`` (``{name: Area}``) with each image area replaced by its
        :class:`~corehq.apps.document_templates.rendering.ImageContent`; an image area
        without an image is left out
    :raises ImageError: if an image cannot be used; the message names the area
    """
    loaded = {}
    for name, area in areas.items():
        if area.type != IMAGE:
            loaded[name] = area
        elif area.value:
            try:
                loaded[name] = ImageContent.from_data(get_image_data(domain, area.value))
            except (ImageError, DocumentRenderError) as error:
                raise ImageError(f'{name}: {error}')
    return loaded


def get_image_url(domain, key):
    return reverse('download_document_template_image', args=[domain, key])
