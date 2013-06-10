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

class CachedObjectMeta(dict):
    content_length = 0
    content_type = ""
    size_key = ""
    meta_type = "object"

    def __init__(self, size_key, content_length, content_type):
        self.size_key = size_key
        self.content_length = content_length
        self.content_type = content_type

    def to_json(self):
        return self.__dict__

    @staticmethod
    def get_extension(content_type):
        splits = content_type.split('/')
        if len(splits) == 2:
            return splits[1]
        else:
            return 'txt'

    @classmethod
    def make_meta(cls, file_obj, size_key, metadata={}):
        """
        giventhe image object and the size key, prepare the metadata calculations
        image_obj: Image object
        size_key: matching the image_size_map - if original calculate from origina lfilesize
        """

        file_obj.seek(0, os.SEEK_END)
        content_type = None
        for ctype_key in ['content_type', 'Content-Type']:
            content_type = metadata.get(ctype_key, None)
            if content_type is not None:
                break
        if content_type is None:
            content_type = 'application/octet-stream'

        ret = cls(
                size_key,
                file_obj.tell(),
                content_type
                  )
        file_obj.seek(0)
        return ret


class CachedImageMeta(CachedObjectMeta):
    height = 0
    width = 0
    meta_type = "image"

    def __init__(self, size_key, width, height, content_length, content_type):
        super(CachedImageMeta, self).__init__(size_key, content_length, content_type)
        self.width = width
        self.height = height

    def get_size(self):
        return self.width, self.height

    @classmethod
    def make_meta(cls, image_obj, image_stream, size_key, metadata={}):
        """
        giventhe image object and the size key, prepare the metadata calculations
        image_obj: Image object
        size_key: matching the image_size_map - if original calculate from origina lfilesize
        """
        #assert isinstance(image_obj, Image), "CachedImageMeta needs to be a PIL Image instance"

        if size_key == OBJECT_ORIGINAL:
            width, height = image_obj.size
        else:
            width = OBJECT_SIZE_MAP[size_key]['width']
            height = OBJECT_SIZE_MAP[size_key]['height']

        image_stream.seek(0, os.SEEK_END)
        content_length = image_stream.tell()
        image_stream.seek(0)

        content_type = metadata.get('content_type', None)
        if content_type is None:
            file_format = image_obj.format
            guessed_type = mimetypes.guess_type("foo.%s" % file_format)
            if guessed_type[0] is not None:
                content_type = guessed_type[0]
            else:
                content_type = 'image/png'

        ret = cls(
            size_key,
            width,
            height,
            content_length,
            content_type
        )
        return ret


class CachedObject(object):
    def __init__(self, filename):
        """
        Filename for a cached object is a user defined, unique, yet human readable identifier.
        """
        self.filename = filename
        #hashed_name is for future use by creating filenames based upon hashes and saving these versions to the filesystem for serving via staticfiles.
        self.hashed_name = hashlib.md5(filename).hexdigest()
        stream_keys, meta_keys = self.get_all_keys()

        self.stream_keys = stream_keys
        self.meta_keys = meta_keys



    @classmethod
    def get_cached(cls, filename):
        pass

    def is_cached(self):
        metas, streams = self.get_all_keys()
        if len(metas) == 0:
            return False
        else:
            return True

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
        return self.get_size(OBJECT_ORIGINAL)

    def get_size(self, size_key):
        """
        Return the stream of the filename and size_key you want
        """
        #stream_key = self.stream_key(size_key)
        #meta_key = self.meta_key(size_key)

        stream = self.fetch_stream(size_key)
        meta = self.fetch_meta(size_key)

        return meta, stream

    def cache_put(self, object_stream, metadata={}):
        object_meta = CachedObjectMeta.make_meta(object_stream, OBJECT_ORIGINAL, metadata=metadata)

        rcache = self.rcache
        object_stream.seek(0)
        rcache.set(self.meta_key(OBJECT_ORIGINAL), simplejson.dumps(object_meta.to_json()))
        rcache.set(self.stream_key(OBJECT_ORIGINAL), object_stream.read())

    @property
    def rcache(self):
        return cache.get_cache('redis')

    def get_all_keys(self):
        stream_keys = self.rcache.keys(self.stream_key(WILDCARD))
        meta_keys = self.rcache.keys(self.meta_key(WILDCARD))

        assert len(stream_keys) == len(meta_keys), "Error stream and meta keys must be 1:1 - something went wrong in the configuration"
        return stream_keys, meta_keys


class CachedImage(CachedObject):

    #for an original, make subsizes on demand
    #get Sizes ofme

    #get all meta
    #filter by filesize
    #generate
    #return stream

    def cache_image(self, image_stream, metadata={}):
        """
        Create a cached image
        For a given original sized image - cache it initially to speed up small size generation
        """
        orig_image_obj = Image.open(image_stream)
        image_meta = CachedImageMeta.make_meta(orig_image_obj, image_stream, OBJECT_ORIGINAL, metadata=metadata)

        rcache = self.rcache
        image_stream.seek(0)

        rcache.set(self.stream_key(OBJECT_ORIGINAL), image_stream.read())
        rcache.set(self.meta_key(OBJECT_ORIGINAL), simplejson.dumps(image_meta.to_json()))

    def get_size(self, size_key):
        """
        Return the stream of the filename and size_key you want
        """
        if not self.has_size(size_key):
            self.make_size(size_key)
        return super(CachedImage, self).get_size(size_key)


    def has_size(self, skey):
        stream_keys, meta_keys = self.get_all_keys()
        if self.stream_key(skey) in stream_keys and self.meta_key(skey) in meta_keys:
            return True
        else:
            return False

    def fetch_image(self, key):
        stream = self.rcache.get(self.stream_key(key))
        if stream is not None:
            source_image_obj = Image.open(StringIO.StringIO(stream))
            return source_image_obj
        else:
            return None

    def make_size(self, size_key):
        """
        size_key = target key size
        """
        rcache = self.rcache
        if self.has_size(size_key):
            #do nothing, already exists
            return 204
        else:
            #make size from the next available largest size (so if there's a small_320 and you want small, generate it from small_320
            size_seq = IMAGE_SIZE_ORDERING.index(size_key)
            source_key = OBJECT_ORIGINAL
            for source_size_key in IMAGE_SIZE_ORDERING[size_seq+1:]:
                if self.has_size(source_size_key):
                    source_key = source_size_key
                    break

            source_size = (OBJECT_SIZE_MAP[source_key]['width'], OBJECT_SIZE_MAP[source_key]['height'])
            source_meta = self.fetch_meta(OBJECT_ORIGINAL)
            target_size = (OBJECT_SIZE_MAP[size_key]['width'], OBJECT_SIZE_MAP[size_key]['height'])
            source_image_obj = self.fetch_image(source_key)


            target_image_obj = ImageOps.fit(source_image_obj, target_size, method=Image.BICUBIC)
            mime_ext = CachedImageMeta.get_extension(source_meta['content_type'])

            #output to buffer
            target_handle = StringIO.StringIO()
            #target_image_obj.save(target_handle, mime_ext)
            target_image_obj.save(target_handle, mime_ext)
            target_handle.seek(0)
            target_meta = CachedImageMeta.make_meta(target_image_obj, target_handle, size_key)

            rcache.set(self.stream_key(size_key), target_handle.read())
            rcache.set(self.meta_key(size_key), simplejson.dumps(target_meta.to_json()))
            return 201





