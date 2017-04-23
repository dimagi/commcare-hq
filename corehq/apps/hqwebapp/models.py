from collections import namedtuple
from django.contrib.auth.models import User
from django.db import models

from corehq.util.markup import mark_up_urls


class GaTracker(namedtuple('GaTracking', 'category action label')):
    """
    Info for tracking clicks using Google Analytics
    see https://developers.google.com/analytics/devguides/collection/analyticsjs/events
    """
    def __new__(cls, category, action, label=None):
        return super(GaTracker, cls).__new__(cls, category, action, label)


class MaintenanceAlert(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=False)

    text = models.TextField()

    class Meta:
        app_label = 'hqwebapp'

    @property
    def html(self):
        return mark_up_urls(self.text)


class HashedPasswordLoginAttempt(models.Model):
    username = models.CharField(max_length=255, db_index=True)
    password_hash = models.CharField(max_length=255)
    used_at = models.DateTimeField(auto_now_add=True)


class UsedPasswords(models.Model):
    user = models.ForeignKey(User, db_index=True)
    password = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)


from .signals import *
