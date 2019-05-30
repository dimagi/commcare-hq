from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

from django.db import models
from .limits import LIMIT_TYPES


class ProjectUsageLimit(models.Model):
    """
    This models allows individual projects change their usage limits form the defaults
    """
    domain = models.CharField(max_length=255, db_index=True)
    limit_name = models.CharField(max_length=255, choices=[
        (limit_type.name, limit_type.description)
        for limit_type in LIMIT_TYPES
    ])
    value = models.IntegerField()

    class Meta(object):
        unique_together = ('domain', 'limit_name')


class ProjectUsageValue(models.Model):
    """
    This model is used to track usage values for individual objects/scopes across a project

    This is where we store the real-time analytics that would allow us to determine
    whether an operation violates a usage limit or not.
    """
    domain = models.CharField(max_length=255)
    # scope can be
    #   - null if it is a project-wide metric
    #   - an object id if it is an object-scoped metric
    scope = models.CharField(max_length=255, null=True)
    limit_name = models.CharField(max_length=255, choices=[
        (limit_type.name, limit_type.description)
        for limit_type in LIMIT_TYPES
    ])
    value = models.IntegerField()

    class Meta(object):
        unique_together = ('domain', 'limit_name', 'scope')
        index_together = ('domain', 'scope')
