from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple

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

    class Meta(object):
        app_label = 'hqwebapp'

    @property
    def html(self):
        return mark_up_urls(self.text)

    def __repr__(self):
        return "MaintenanceAlert(text='{}', active='{}')".format(self.text, self.active)


from .signals import *
