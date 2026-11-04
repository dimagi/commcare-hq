import uuid
from io import BytesIO

from couchdbkit import ResourceNotFound
from PIL import Image

from corehq.apps.hqmedia.models import CommCareImage


def make_image(format='PNG'):
    """Return a small image with a random color, so each upload is distinct"""
    buffer = BytesIO()
    Image.new('RGB', (10, 20), color=tuple(uuid.uuid4().bytes[:3])).save(buffer, format=format)
    return buffer.getvalue()


def delete_image(image_id):
    try:
        CommCareImage.get(image_id).delete()
    except ResourceNotFound:
        pass
