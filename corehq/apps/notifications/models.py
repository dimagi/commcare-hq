from django.contrib.auth.models import User
from django.db import models


class Notification(models.Model):
    types = (
        ('info', 'Product Notification'),
        ('alert', 'Maintenance Notification'),
    )
    content = models.CharField(max_length=140)
    url = models.URLField()
    type = models.CharField(max_length=10, choices=types)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    users_read = models.ManyToManyField(User)
    is_active = models.BooleanField(default=False)
    activated = models.DateTimeField(db_index=True, null=True, blank=True)

    class Meta:
        ordering = ["-activated"]
