from django.db import models
from imagekit.models import ImageModel


class Photo(ImageModel):
    name = models.CharField(max_length=100)
    original_image = models.ImageField(upload_to='static/photos')#(upload_to='apps/photos/static')
    num_views   = models.PositiveIntegerField(editable=False, default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class IKOptions:
        # This inner class is where we define the ImageKit options for the model
        spec_module = 'photos.specs'
        cache_dir = 'data/photos'
        image_field = 'original_image'
        save_count_as = 'num_views'
        
    
    class Meta:
        ordering = ['-created_at']
        