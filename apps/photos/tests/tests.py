import unittest
import os

from photos.models import Photo


class TestPhotos(unittest.TestCase):

    def setup(self):
        p = Photo("test image", original_image="apps/photos/tests/test.jpg")
        p.save()