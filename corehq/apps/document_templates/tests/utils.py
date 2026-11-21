import uuid
from io import BytesIO

from couchdbkit import ResourceNotFound
from PIL import Image

from corehq.apps.hqmedia.models import CommCareImage


def make_image(format='PNG', size=(10, 20)):
    """Return a half-transparent image with a random color, so each upload is distinct"""
    buffer = BytesIO()
    color = (*uuid.uuid4().bytes[:3], 128)
    Image.new('RGBA', size, color=color).save(buffer, format=format)
    return buffer.getvalue()


def delete_image(image_id):
    try:
        CommCareImage.get(image_id).delete()
    except ResourceNotFound:
        pass
