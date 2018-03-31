from __future__ import absolute_import
from __future__ import unicode_literals
from django.dispatch import Signal

location_edited = Signal(providing_args=['loc', 'moved'])
