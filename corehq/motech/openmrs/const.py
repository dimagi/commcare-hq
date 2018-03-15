from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from django.utils.translation import ugettext_lazy as _


LOG_LEVEL_CHOICES = (
    (99, 'Disable logging'),
    (logging.ERROR, 'Error'),
    (logging.INFO, 'Info'),
)

IMPORT_FREQUENCY_WEEKLY = 'weekly'
IMPORT_FREQUENCY_MONTHLY = 'monthly'
IMPORT_FREQUENCY_CHOICES = (
    (IMPORT_FREQUENCY_WEEKLY, _('Weekly')),
    (IMPORT_FREQUENCY_MONTHLY, _('Monthly')),
)
