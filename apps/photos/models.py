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
        