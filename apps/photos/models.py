from django.db import models
from imagekit.models import ImageModel
import settings

class Photo(ImageModel):
    name = models.CharField(max_length=100)
    original_image = models.ImageField(upload_to='/tmp') # upload_to is meaningless since we get the photos via xform, but it's required by ImageModel
    num_views   = models.PositiveIntegerField(editable=False, default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class IKOptions:
        # This inner class is where we define the ImageKit options for the model
        spec_module = 'photos.specs'
        cache_dir = settings.RAPIDSMS_APPS['photos']['image_path']
        image_field = 'original_image'
        save_count_as = 'num_views'
        
    
    class Meta:
        ordering = ['-created_at']


'''
    This isn't really supposed to work as a test right now, it's more to describe how to use the system

    >>> p = Photo(name="test image", original_image="apps/photos/tests/test.jpg")
    >>> p.save()
    >>> n = p.name
    >>> i = Photo.objects.get(name=n)
    >>> i.display.url
    u'/data/photos/test_display.jpg'
    >>> from django.test.client import Client
    >>> c = Client()
    >>> resp = c.get('/data/photos/test_display.jpg')
    >>> resp.status_code
    200
    >>> resp = c.get('/photo/%s' % i.id)
    >>> resp.status_code
    200
'''
