from django.db import models


class SidecarApp(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    created_on = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    url = models.URLField()

    class Meta:
        unique_together = ('domain', 'slug')
