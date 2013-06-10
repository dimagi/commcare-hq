import hashlib
import mimetypes
import os
import simplejson

try:
    import cStringIO as StringIO
except:
    import StringIO

from django.core import cache
from PIL import Image, ImageOps

CACHE_PREFIX = 'ocache_'

IMAGE_SIZE_SQUARE = 'square'
IMAGE_SIZE_LARGE_SQUARE = 'large_square'
IMAGE_SIZE_THUMBNAIL = 'thumbnail'
IMAGE_SIZE_SMALL = 'small'
IMAGE_SIZE_SMALL_320 = 'small_320'
IMAGE_SIZE_MEDIUM = 'medium'
IMAGE_SIZE_MEDIUM_640 = 'medium_640'
IMAGE_SIZE_MEDIUM_800 = 'medium_800'
IMAGE_SIZE_LARGE = 'large'
IMAGE_SIZE_720 = '720'
IMAGE_SIZE_1080 = '1080'
IMAGE_SIZE_HUGE = 'huge'

IMAGE_SIZE_ORIGINAL = 'original'
IMAGE_SIZE_WILDCARD = '*'

#grr, since ordered_dict is 2.7 only
IMAGE_SIZE_ORDERING = [
    IMAGE_SIZE_SQUARE,
    IMAGE_SIZE_THUMBNAIL,
    IMAGE_SIZE_LARGE_SQUARE,
    IMAGE_SIZE_SMALL,
    IMAGE_SIZE_SMALL_320,
    IMAGE_SIZE_MEDIUM,
    IMAGE_SIZE_MEDIUM_640,
    IMAGE_SIZE_MEDIUM_800,
    IMAGE_SIZE_LARGE,
    IMAGE_SIZE_720,
    IMAGE_SIZE_1080,
    IMAGE_SIZE_HUGE,
    IMAGE_SIZE_ORIGINAL
]

OBJECT_SIZE_MAP = {
    #somebody stop me, so many choices!
    IMAGE_SIZE_SQUARE: {"width": 75, "height": 75},
    IMAGE_SIZE_LARGE_SQUARE: {"width": 140, "height": 140}, #140 is tbootstrap's img div 150 is flickr
    IMAGE_SIZE_THUMBNAIL: {"width": 100, "height": 75},
    IMAGE_SIZE_SMALL: {"width": 240, "height": 180},
    IMAGE_SIZE_SMALL_320: {"width": 320, "height": 240},
    IMAGE_SIZE_MEDIUM: {"width": 500, "height": 375},
    IMAGE_SIZE_MEDIUM_640: {"width": 640, "height": 480},
    IMAGE_SIZE_MEDIUM_800: {"width": 800, "height": 600},
    IMAGE_SIZE_LARGE: {"width": 1024, "height": 768},
    IMAGE_SIZE_720: {"width": 1280, "height": 720},
    IMAGE_SIZE_1080: {"width": 1920, "height": 1080},
    IMAGE_SIZE_HUGE: {"width": 3000, "height": 2000}, #largest

    IMAGE_SIZE_ORIGINAL: {"width": 0, "height": 0} #cache the original anyway - but generally don't serve this
}

class CachedObjectMeta(dict):
    content_length = 0
    content_type = ""
    size_key = ""
    meta_type = "object"

    def __init__(self, size_key, content_length, content_type):
        self.size_key = size_key
        self.content_length = content_length
        self.content_type = content_type

    @staticmethod
    def get_extension(content_type):
        splits = content_type.split('/')
        if len(splits) == 2:
            return splits[1]
        else:
            return 'txt'

    @classmethod
    def make_meta(cls, file_obj, size_key):
        """
        giventhe image object and the size key, prepare the metadata calculations
        image_obj: Image object
        size_key: matching the image_size_map - if original calculate from origina lfilesize
        """

        cls.size_key = size_key

        file_obj.seek(0, os.SEEK_END)
        cls.content_length = file_obj.tell()
        file_obj.seek(0)

        file_format = file_obj.format
        guessed_type = mimetypes.guess_type("foo.%s" % file_format)
        if guessed_type[0] is not None:
            cls.content_type = guessed_type[0]


class CachedImageMeta(CachedObjectMeta):
    height = 0
    width = 0
    meta_type = "image"

    def __init__(self, size_key, height, width, content_length, content_type):
        super(CachedImageMeta, self).__init__(size_key, content_length, content_type)
        self.height = height
        self.width = width

    def get_size(self):
        return self.width, self.height

    @classmethod
    def make_meta(cls, image_obj, size_key):
        """
        giventhe image object and the size key, prepare the metadata calculations
        image_obj: Image object
        size_key: matching the image_size_map - if original calculate from origina lfilesize
        """
        assert isinstance(image_obj, Image), "CachedImageMeta needs to be a PIL Image instance"

        if size_key == IMAGE_SIZE_ORIGINAL:
            width, height = image_obj.size
        else:
            width = OBJECT_SIZE_MAP[size_key]['width']
            height = OBJECT_SIZE_MAP[size_key]['height']

        cls.size_key = size_key
        cls.width = width
        cls.height = height
        cls.content_length = image_obj.fp.len
        file_format = image_obj.format
        guessed_type = mimetypes.guess_type("foo.%s" % file_format)
        if guessed_type[0] is not None:
            cls.content_type = guessed_type[0]


class CachedObject(object):
    def __init__(self, filename, object_stream):
        """

        """
        self.filename = filename
        #hashed_name is for future use by creating filenames based upon hashes and saving these versions to the filesystem for serving via staticfiles.
        self.hashed_name = hashlib.md5(filename).hexdigest()
        self.object_stream = object_stream

    @property
    def key_prefix(self):
        #reality is it's the filename
        #note single underscore here and on the other side so it's double underscore
        return "%(cache_prefix)s_%(prefix_str)s_" % {"cache_prefix": CACHE_PREFIX,
                                                     "prefix_str": self.filename}

    def stream_key(self, size_key):
        cache_stream_key = "%(prefix)s_object_%(size)s" % \
                           {"prefix": self.key_prefix,
                            "size": size_key}
        return cache_stream_key

    def meta_key(self, size_key):
        cache_meta_key = "%(prefix)s_meta_%(size)s" % \
                         {"prefix": self.key_prefix, "size": size_key}
        return cache_meta_key

    def rcache(self):
        return cache.get_cache('redis')

    @classmethod
    def get_size(cls, filename, size_key):
        """
        Return the stream of the filename and size_key you want
        """
        pass

    def get_sizes(self):
        rcache = self.rcache()
        stream_keys = rcache.get(self.stream_key(IMAGE_SIZE_WILDCARD))
        meta_keys = rcache.get(self.meta_key(IMAGE_SIZE_WILDCARD))

        assert len(stream_keys) == len(meta_keys), "Error stream and meta keys must be 1:1 - something went wrong in the configuration"
        return stream_keys, meta_keys

    def get_sizes(self):
        rcache = self.rcache()
        all_keys = rcache.get("%s*" % self.key_prefix)
        stream_keys = filter(lambda x: x[len(self.key_prefix):].startswith('_image'), all_keys)
        meta_keys = filter(lambda x: x[len(self.key_prefix):].startswith('_meta'), all_keys)
        return stream_keys, meta_keys

    @classmethod
    def cache_object(cls, filename, object_stream):
        ret = cls(filename, object_stream)

        image_meta = CachedObjectMeta.make_meta(orig_image_obj, IMAGE_SIZE_ORIGINAL)

        rcache = ret.rcache()

        image_stream.fp.seek(0)
        rcache.set(ret.stream_key(IMAGE_SIZE_ORIGINAL), image_stream.fp.read())
        rcache.set(ret.meta_key(IMAGE_SIZE_ORIGINAL), simplejson.dumps(image_meta))
        return ret



class CachedImage(CachedObject):

    #for an original, make subsizes on demand
    #get Sizes ofme

    #get all meta
    #filter by filesize
    #generate
    #return stream


    @classmethod
    def cache_image(cls, filename, image_stream):
        """
        Create a cached image
        For a given original sized image - cache it initially to speed up small size generation
        """
        orig_image_obj = Image.open(StringIO.StringIO(image_stream))
        ret = cls(filename, image_stream)

        image_meta = CachedImageMeta.make_meta(orig_image_obj, IMAGE_SIZE_ORIGINAL)

        rcache = ret.rcache()

        image_stream.fp.seek(0)
        rcache.set(ret.stream_key(IMAGE_SIZE_ORIGINAL), image_stream.fp.read())
        rcache.set(ret.meta_key(IMAGE_SIZE_ORIGINAL), simplejson.dumps(image_meta))
        return ret

    def make_size(self, size_key):
        """
        size_key = target key size
        """
        rcache = self.rcache()

        stream_keys, meta_keys = self.get_sizes()

        def has_size(skey):
            if self.stream_key(skey) in stream_keys and self.meta_key(skey) in meta_keys:
                return True
            else:
                return False

        if has_size(size_key):
            #do nothing, already exists
            return 204
        else:
            #make size from the next available largest size (so if there's a small_320 and you want small, generate it from small_320
            size_seq = IMAGE_SIZE_ORDERING.index(size_key)
            source_key = IMAGE_SIZE_ORIGINAL
            for source_size_key in IMAGE_SIZE_ORDERING[size_seq+1:]:
                if has_size(source_size_key):
                    source_key = source_size_key
                    break
            source_size = (OBJECT_SIZE_MAP[source_key]['width'], OBJECT_SIZE_MAP[source_key]['height'])
            target_size = (OBJECT_SIZE_MAP[size_key]['width'], OBJECT_SIZE_MAP[size_key]['height'])

            source_image_obj = Image.open(StringIO.StringIO(rcache.get(self.stream_key(source_key))))
            target_image_obj = ImageOps.fit(source_image_obj, target_size, method=Image.BICUBIC)
            mime_ext = CachedImageMeta.get_extension(meta_keys[0])

            #output to buffer
            target_handle = StringIO.StringIO()
            target_image_obj.save(target_handle, mime_ext)
            target_handle.seek(0)
            target_meta = CachedImageMeta.make_meta(target_image_obj, size_key)

            rcache.set(self.stream_key(size_key), target_image_obj.fp.read())
            rcache.set(self.meta_key(size_key), simplejson.dumps(target_meta))
            return 201





