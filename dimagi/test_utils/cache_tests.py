import os
import StringIO

from PIL import Image
from unittest2 import TestCase

from dimagi.utils.django import cached_object
from dimagi.utils.django.cached_object import CachedObject, CachedImage, IMAGE_SIZE_ORDERING, OBJECT_ORIGINAL

class FakeCache(object):
    def __init__(self):
        self.cache_dict = {}

    def get(self, key):
        return self.cache_dict.get(key, None)

    def keys(self, pattern):
        all_keys = self.cache_dict.keys()
        filtered = filter(lambda x: x.startswith(pattern[:-1]), all_keys)
        return filtered

    def set(self, key, value):
        self.cache_dict[key] = value


fake_cache = FakeCache()
cached_object.MOCK_REDIS_CACHE = fake_cache

class CachedObjectTests(TestCase):

    def SetUp(self):
        cached_object.MOCK_REDIS_CACHE = fake_cache

    def testBasicObjects(self):
        text = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        filename = "something"
        buffer = StringIO.StringIO(text)

        obj = CachedObject(filename)

        self.assertFalse(obj.is_cached())
        metadata = {'content_type': 'text/plain'}
        obj.cache_put(buffer, metadata)

        self.assertTrue(obj.is_cached())
        cmeta, cstream = obj.get()
        self.assertEqual(cmeta['content_length'], len(text))
        self.assertEqual(cstream.read(), text)


    def _make_image(self, width=3001, height=2001):
        im = Image.new("RGB", (width, height), (0, 0, 0))
        buf = StringIO.StringIO()
        im.save(buf, "png")
        buf.seek(0)
        return (im, buf)

    def testHugeImageObject(self):
        image, buffer = self._make_image()
        buffer.seek(0, os.SEEK_END)
        orig_size = buffer.tell()
        buffer.seek(0)

        cimage = CachedImage("test_huge")
        metadata = {'content_type': 'image/png'}
        cimage.cache_image(buffer, metadata)

        for size in IMAGE_SIZE_ORDERING:
            self.assertTrue(cimage.can_size(size))

            cmeta, cstream = cimage.get_size(size)
            self.assertEqual(cmeta['size_key'], size)
            cstream.seek(0, os.SEEK_END)
            stream_size = cstream.tell()

            if size != OBJECT_ORIGINAL:
                self.assertLess(stream_size, orig_size)
            else:
                self.assertEqual(stream_size, orig_size)


    def testSmallerImageObject(self):
        image, buffer = self._make_image(width=641, height=481)
        buffer.seek(0, os.SEEK_END)
        orig_size = buffer.tell()
        buffer.seek(0)

        cimage = CachedImage("test_small")
        metadata = {'content_type': 'image/png'}
        cimage.cache_image(buffer, metadata)

        smaller = IMAGE_SIZE_ORDERING[0:7]
        bigger = IMAGE_SIZE_ORDERING[7:-1] # skip the original

        for size_key in smaller:
            self.assertTrue(cimage.can_size(size_key))

            cmeta, cstream = cimage.get_size(size_key)
            self.assertEqual(cmeta['size_key'], size_key)
            cstream.seek(0, os.SEEK_END)
            stream_size = cstream.tell()
            self.assertLess(stream_size, orig_size)

        for size_key in bigger:
            self.assertFalse(cimage.can_size(size_key), msg="size key: %s shouldn't be sized" % size_key)
            cmeta, cstream = cimage.get_size(size_key)
            cstream.seek(0, os.SEEK_END)
            stream_size = cstream.tell()
            self.assertEqual(stream_size, orig_size)
            self.assertNotEqual(cmeta['size_key'], size_key)
            self.assertEqual(cmeta['size_key'], OBJECT_ORIGINAL)











