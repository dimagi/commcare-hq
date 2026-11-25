import uuid
from io import BytesIO

from PIL import Image

from corehq.blobs import get_blob_db


def make_image(format='PNG', size=(10, 20), exif=None):
    """Return an image with a random color, so each upload is distinct; half-transparent unless JPEG"""
    buffer = BytesIO()
    mode, color = ('RGB', tuple(uuid.uuid4().bytes[:3])) if format == 'JPEG' else (
        'RGBA', (*uuid.uuid4().bytes[:3], 128))
    options = {'exif': exif} if exif else {}
    Image.new(mode, size, color=color).save(buffer, format=format, **options)
    return buffer.getvalue()


def delete_image(key):
    get_blob_db().delete(key=key)
