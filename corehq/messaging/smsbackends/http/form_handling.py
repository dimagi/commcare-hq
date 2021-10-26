from corehq.util.validation import is_url_or_host_banned
from corehq.util.urlvalidate.ip_resolver import CannotResolveHost
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _


def form_clean_url(url):
    try:
        if is_url_or_host_banned(url):
            raise ValidationError(_("Invalid URL"))
    except CannotResolveHost:
        raise ValidationError(_("Cannot Resolve URL"))

    return url
