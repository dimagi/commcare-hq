import uuid
from io import BytesIO

from couchdbkit import ResourceNotFound
from PIL import Image

from corehq.apps.hqmedia.models import CommCareImage


def png_bytes():
    """PNG bytes that are unique, because hqmedia shares images with the same content"""
    buffer = BytesIO()
    Image.new('RGB', (10, 20), color=tuple(uuid.uuid4().bytes[:3])).save(buffer, format='PNG')
    return buffer.getvalue()


def delete_image(image_id):
    try:
        CommCareImage.get(image_id).delete()
    except ResourceNotFound:
        pass  # saved twice, deleted already
