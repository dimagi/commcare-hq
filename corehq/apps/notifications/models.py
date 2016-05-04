from django.contrib.auth.models import User
from django.db import models


class Notification(models.Model):
    types = (
        ('info', 'info'),
        ('alert', 'alert'),
    )
    content = models.CharField(max_length=140)
    url = models.URLField()
    type = models.CharField(max_length=10, choices=types)
    created = models.DateTimeField(auto_now_add=True)
    users_read = models.ManyToManyField(User)

    class Meta:
        ordering = ["-created"]
