from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.translations.models import TransifexProject


def transifex_details_available_for_domain(domain):
    return TransifexProject.objects.filter(domain=domain).exists()
