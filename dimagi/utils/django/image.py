from django.core import cache

IMAGE_SIZES = {
    "square": {"width": 75, "height": 75},
    "large_square": {"width": 140, "height": 140}, #140 is tbootstrap's img div 150 is flickr
    "thumbnail": {"width": 100, "height": 75},
    "small": {"width": 240, "height": 180},
    "small_320": {"width": 320, "height": 240},
    "medium": {"width": 500, "height": 375},
    "medium_640": {"width": 640, "height": 480},
    "medium_800": {"width": 800, "height": 600},
    "large": {"width": 1024, "height": 768},
    "720": {"width": 1280, "height": 720},
    "1080": {"width": 1920, "height": 1080},
    "original": {"width": 3000, "height": 2000},
}

class CachedImage(object):

    #for an original, make subsizes on demand
    #get Sizes ofme

    #get all meta
    #filter by filesize
    #generate
    #return stream

    def rcache(self):
        return cache.get_cache('redis')

    def __init__(self, filename, image_obj):
        pass

    @classmethod
    def get_size(cls, filename, size_key):



        pass

    def get_sizes(self):
        pass

    def generate_size(self, size_key):
        pass

    def getSizes(self):
        pass
