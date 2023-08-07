import io
import os
from PIL import Image, ImageOps
from testil import eq

THUMBNAIL_SIZE = (211, 32)


def _get_logo():
    with open(os.path.join(os.path.dirname(__file__), 'data', 'commcare.png'), "rb") as f:
        return Image.open(io.BytesIO(f.read()))


def test_thumbnail_resize_works():
    logo = _get_logo()
    logo.load()
    logo.thumbnail(THUMBNAIL_SIZE)
    logo.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)


def test_rgb_conversion():
    logo = _get_logo()
    logo.convert('RGB')


def test_image_size():
    logo = _get_logo()
    eq(logo.size, (360, 84))


def test_save():
    logo = _get_logo()
    logo.save("/tmp/commcarehq", 'PNG')


def test_image_ops_fit():
    logo = _get_logo()
    target_logo = ImageOps.fit(
        logo,
        (200, 100),
        method=Image.Resampling.BICUBIC
    )
    eq(target_logo.size, (200, 100))
