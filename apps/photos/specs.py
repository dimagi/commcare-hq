from imagekit.specs import ImageSpec 
from imagekit import processors 

# allocate more memory to PIL to avoid "encoder error -2" : http://mail.python.org/pipermail/image-sig/1999-August/000816.html
import ImageFile
ImageFile.MAXBLOCK = 1000000


class ResizeThumb(processors.Resize): 
    width   = 120 
    height  = 100
    crop = True

class ResizeDisplay(processors.Resize):
    width = 640 

# class EnchanceThumb(processors.Adjustment): 
#     contrast = 1.2 
#     sharpness = 1.1 



class Thumbnail(ImageSpec): 
    access_as = 'thumbnail' 
    pre_cache = True 
    processors = [ResizeThumb] #, EnchanceThumb] 

class Display(ImageSpec):
    increment_count = True
    processors = [ResizeDisplay]

class Fullsize(ImageSpec):
    increment_count = True
    access_as = 'fullsize' 
    pre_cache = True
    