from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _


LowercaseAlphanumericValidator = RegexValidator(
    r'^[a-z0-9]*$',
    message=_('must be lowercase alphanumeric'),
    code='invalid_lowercase_alphanumeric'
)
