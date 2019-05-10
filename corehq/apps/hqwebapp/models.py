from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple

from django.db import models
from django.contrib.postgres.fields import ArrayField

from corehq.util.quickcache import quickcache
from corehq.util.markup import mark_up_urls


PageInfoContext = namedtuple('PageInfoContext', 'title url')


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
    domains = ArrayField(models.CharField(max_length=126), null=True)

    class Meta(object):
        app_label = 'hqwebapp'

    @property
    def html(self):
        return mark_up_urls(self.text)

    def __repr__(self):
        return "MaintenanceAlert(text='{}', active='{}', domains='{}')".format(
            self.text, self.active, ", ".join(self.domains) if self.domains else "All Domains")

    def save(self, *args, **kwargs):
        MaintenanceAlert.get_latest_alert.clear(MaintenanceAlert)
        super(MaintenanceAlert, self).save(*args, **kwargs)

    @classmethod
    @quickcache([], timeout=60 * 60)
    def get_latest_alert(cls):
        active_alerts = cls.objects.filter(active=True).order_by('-modified')
        if active_alerts:
            return active_alerts[0]
        else:
            return ''


from .signals import *
