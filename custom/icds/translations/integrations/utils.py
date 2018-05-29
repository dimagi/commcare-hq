from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings


def transifex_details_available_for_domain(domain):
    return (
        settings.TRANSIFEX_DETAILS and
        settings.TRANSIFEX_DETAILS.get('project', {}).get(domain)
    )
