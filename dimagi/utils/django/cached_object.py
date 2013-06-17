import hashlib
import mimetypes
import os
import uuid
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

OBJECT_ORIGINAL = 'original'
WILDCARD = '*'

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
    OBJECT_ORIGINAL
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

    OBJECT_ORIGINAL: {"width": 0, "height": 0} #cache the original anyway - but generally don't serve this
}

MOCK_REDIS_CACHE = None

class CachedObjectMeta(dict):
    content_length = 0
    content_type = ""
    size_key = ""
    meta_type = "object"

    def __init__(self, size_key=OBJECT_ORIGINAL, content_length=0, content_type='application/octet-stream'):
        self.size_key = size_key
        self.content_length = content_length
        self.content_type = content_type

    def to_json(self):
        return self.__dict__

    @classmethod
    def wrap(cls, data):
        ret = cls(size_key=data['size_key'], content_length=data['content_length'], content_type=data['content_type'])
        ret.__dict__ = data
        return ret

    @staticmethod
    def get_extension(content_type):
        splits = content_type.split('/')
        if len(splits) == 2:
            return splits[1]
        else:
            return 'txt'

    @classmethod
    def make_meta(cls, file_stream, size_key, metadata):
        """
        Given the image object and the size key, prepare the metadata calculations
        image_obj: Image object
        file_stream: StringIO stream
        size_key: matching the image_size_map - if original calculate from the original file
        metadata: dict of attachment information taken from the couch _attachments dict
        """
        file_stream.seek(0, os.SEEK_END)
        content_type = None
        for ctype_key in ['content_type', 'Content-Type']:
            content_type = metadata.get(ctype_key, None)
            if content_type is not None:
                break
        if content_type is None:
            content_type = 'application/octet-stream'

        ret = cls(size_key=size_key,
                  content_length=file_stream.tell(),
                  content_type=content_type
        )
        file_stream.seek(0)
        return ret


class CachedImageMeta(CachedObjectMeta):
    height = 0
    width = 0
    meta_type = "image"

    def __init__(self, size_key=OBJECT_ORIGINAL, width=0, height=0, content_length=0, content_type='application/octet-stream'):
        super(CachedImageMeta, self).__init__(size_key=size_key, content_length=content_length, content_type=content_type)
        self.width = width
        self.height = height

    def get_image_size(self):
        return (self.width, self.height)

    @classmethod
    def make_meta(cls, file_stream, size_key, metadata):
        """
        Given the image object and the size key, prepare the metadata calculations
        image_obj: Image object
        size_key: matching the image_size_map - if original calculate from origina lfilesize
        """
        file_stream.seek(0)
        image_obj = Image.open(file_stream)

        if size_key == OBJECT_ORIGINAL:
            width, height = image_obj.size
        else:
            width = OBJECT_SIZE_MAP[size_key]['width']
            height = OBJECT_SIZE_MAP[size_key]['height']

        file_stream.seek(0, os.SEEK_END)
        content_length = file_stream.tell()
        file_stream.seek(0)

        content_type='application/octet-stream'
        for ctype_key in ['content_type', 'Content-Type']:
            content_type = metadata.get(ctype_key, None)
            if content_type is not None:
                break

        ret = cls(
            size_key=size_key,
            width=width,
            height=height,
            content_length=content_length,
            content_type=content_type
        )
        return ret


class CachedObject(object):
    def __init__(self, cache_key):
        """
        cache_key is the supposedly unique cache key you will want to create for keeping track of your cacheable assets.
        like cache.set(key, value) - it's the implementor's responsibility to make sure to have a universally unique cache key for the assets you want to cache.
        """
        self.cache_key = cache_key

        #key_hash is the hash of the key for eventual use as a retrieval via static assets.
        #todo: once key_hash determined with object stream, create stream file and deposit onto static machine
        #generate url and retrieve by key_hash url.
        self.key_hash = hashlib.md5(cache_key).hexdigest()
        stream_keys, meta_keys = self.get_all_keys()

        self.stream_keys = stream_keys
        self.meta_keys = meta_keys

    def is_cached(self):
        metas, streams = self.get_all_keys()
        if len(metas) == 0:
            return False
        else:
            return True

    @property
    def key_prefix(self):
        #reality is it's the cache_key
        #note single underscore here and on the other side so it's double underscore
        return "%(cache_prefix)s_%(prefix_str)s_" % {"cache_prefix": CACHE_PREFIX,
                                                     "prefix_str": self.cache_key}

    def stream_key(self, size_key):
        cache_stream_key = "%(prefix)s_object_%(size)s" % \
                           {"prefix": self.key_prefix,
                            "size": size_key}
        return cache_stream_key

    def meta_key(self, size_key):
        cache_meta_key = "%(prefix)s_meta_%(size)s" % \
                         {"prefix": self.key_prefix, "size": size_key}
        return cache_meta_key

    def fetch_stream(self, key):
        stream = self.rcache.get(self.stream_key(key))
        if stream is not None:
            return StringIO.StringIO(stream)
        else:
            return None

    def fetch_meta(self, key):
        meta = self.rcache.get(self.meta_key(key))
        if meta is not None:
            return simplejson.loads(meta)
        else:
            return {}

    #retrieval methods
    def get(self):
        return self._do_get_size(OBJECT_ORIGINAL)

    def _do_get_size(self, size_key):
        """
        Return the stream of the cache_key and size_key you want
        """
        stream = self.fetch_stream(size_key)
        meta = self.fetch_meta(size_key)

        return (meta, stream)

    def cache_put(self, object_stream, metadata):
        object_meta = CachedObjectMeta.make_meta(object_stream, OBJECT_ORIGINAL, metadata)

        rcache = self.rcache
        object_stream.seek(0)
        rcache.set(self.stream_key(OBJECT_ORIGINAL), object_stream.read())
        rcache.set(self.meta_key(OBJECT_ORIGINAL), simplejson.dumps(object_meta.to_json()))

    @property
    def rcache(self):
        return MOCK_REDIS_CACHE or cache.get_cache('redis')

    def get_all_keys(self):
        """
        Returns all FULL keys
        """
        full_stream_keys = self.rcache.keys(self.stream_key(WILDCARD))
        full_meta_keys = self.rcache.keys(self.meta_key(WILDCARD))

        assert len(full_stream_keys) == len(full_meta_keys), "Error stream and meta keys must be 1:1 - something went wrong in the configuration"
        return full_stream_keys, full_meta_keys


class CachedImage(CachedObject):
    """
    Image specific operations added to Cached Object. Specifically resolution resizing
    """
    def cache_image(self, image_stream, metadata):
        """
        Create a cached image
        For a given original sized image - cache it initially to speed up small size generation
        """
        image_meta = CachedImageMeta.make_meta(image_stream, OBJECT_ORIGINAL, metadata)

        rcache = self.rcache
        image_stream.seek(0)

        rcache.set(self.stream_key(OBJECT_ORIGINAL), image_stream.read())
        rcache.set(self.meta_key(OBJECT_ORIGINAL), simplejson.dumps(image_meta.to_json()))

    def fetch_image(self, key):
        stream = self.rcache.get(self.stream_key(key))
        if stream is not None:
            source_image_obj = Image.open(StringIO.StringIO(stream))
            return source_image_obj
        else:
            #if the stream is None, then that means that size is too big.
            #walk all sizes from here on out till we get a stream.
            size_idx = IMAGE_SIZE_ORDERING.index(key)

            for skey in IMAGE_SIZE_ORDERING[size_idx:]:
                next_stream = self.rcache.get(self.stream_key(skey))
                if next_stream is not None:
                    source_image_obj = Image.open(StringIO.StringIO(next_stream))
                    #will eventually return original
                    return source_image_obj
                else:
                    continue
            return None

    def get_size(self, size_key):
        """
        Return the stream of the cache_key and size_key you want
        """
        if not self.has_size(size_key):
            can_size = self.can_size(size_key)
            if can_size:
                self.make_size(size_key)
            else:
                #if size is not possible, this will mean it's too large, return the original
                size_key = OBJECT_ORIGINAL
        return super(CachedImage, self)._do_get_size(size_key)


    def can_size(self, target_size_key, source_size_key=OBJECT_ORIGINAL):
        """
        Given the size, can an intermediate resolution scaled image be made constrain only by width
        """
        source_meta = CachedImageMeta.wrap(self.fetch_meta(source_size_key))
        target_size = (OBJECT_SIZE_MAP[target_size_key]['width'], OBJECT_SIZE_MAP[target_size_key]['height'])

        if source_meta.width < target_size[0]:
            return False
        else:
            return True

    def has_size(self, size_key):
        """
        Is a given sized image cached already
        """
        full_stream_keys, full_meta_keys = self.get_all_keys()
        if self.stream_key(size_key) in full_stream_keys and self.meta_key(size_key) in full_meta_keys:
            return True
        else:
            return False

    def make_size(self, size_key):
        """
        size_key = target key size

        returns: Nothing
        """
        rcache = self.rcache
        if not self.has_size(size_key):
            #make size from the next available largest size (so if there's a small_320 and you want small, generate it from next size up
            size_seq = IMAGE_SIZE_ORDERING.index(size_key)
            source_key = OBJECT_ORIGINAL
            target_size = (OBJECT_SIZE_MAP[size_key]['width'], OBJECT_SIZE_MAP[size_key]['height'])

            for source_size_key in IMAGE_SIZE_ORDERING[size_seq+1:]:
                if self.has_size(source_size_key):
                    source_key = source_size_key
                    break

            source_meta = CachedImageMeta.wrap(self.fetch_meta(OBJECT_ORIGINAL))

            if source_meta.width <= target_size[0]:
                rcache.set(self.stream_key(size_key), "")
                rcache.set(self.meta_key(size_key), simplejson.dumps(source_meta.to_json()))
            else:
                source_image_obj = self.fetch_image(source_key)

                target_image_obj = ImageOps.fit(source_image_obj, target_size, method=Image.BICUBIC)
                mime_ext = CachedImageMeta.get_extension(source_meta.content_type)

                #output to buffer
                target_handle = StringIO.StringIO()
                target_image_obj.save(target_handle, mime_ext)
                target_handle.seek(0)
                target_meta = CachedImageMeta.make_meta(target_handle, size_key, metadata={'content_type': source_meta.content_type})

                rcache.set(self.stream_key(size_key), target_handle.read())
                rcache.set(self.meta_key(size_key), simplejson.dumps(target_meta.to_json()))





