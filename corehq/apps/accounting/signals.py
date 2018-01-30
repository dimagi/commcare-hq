from __future__ import absolute_import
from __future__ import unicode_literals
from django.dispatch import Signal

subscription_upgrade_or_downgrade = Signal(providing_args=["domain"])
