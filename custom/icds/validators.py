
from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _


HostedCCZLinkIdentifierValidator = RegexValidator(
    r'^[a-z0-9_-]*$',
    message=_('must contain lowercase alphanumeric or - or _'),
    code='invalid_hosted_ccz_link_identifier'
)
