from django.db import models
from imagekit.models import ImageModel

class Photo(ImageModel):
    name = models.CharField(max_length=100)
    original_image = models.ImageField(upload_to='photos')
    num_views = models.PositiveIntegerField(editable=False, default=0)

    class IKOptions:
        # This inner class is where we define the ImageKit options for the model
        spec_module = 'imagehandler.specs'
        cache_dir = 'photos'
        image_field = 'original_image'
        save_count_as = 'num_views'
