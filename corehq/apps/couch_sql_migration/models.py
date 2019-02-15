from __future__ import absolute_import
from django.db import models
"""
Models for storing temporary data for domain migrations
"""


class Undo(models.Model):
    """
    Stores the last value of an object property.

    Used for undoing values that are changed by migrations where the
    source domain is different from the destination domain.
    """
    src_domain = models.CharField(max_length=255, db_index=True)
    obj_class = models.CharField(max_length=255)
    obj_id = models.CharField(max_length=255)
    obj_property = models.CharField(max_length=255)
    # We don't care about historical values. Just the last one.
    last_value = models.TextField()

    class Meta:
        # A property can't have more than one "last_value"
        unique_together = ('src_domain', 'obj_class', 'obj_id', 'obj_property')
