import datetime

from django.utils import timezone

from corehq.apps.public_webforms.models import PublicWebform

DOMAIN = 'public-forms-domain'


def create_webform(**kwargs):
    return PublicWebform.objects.create(**{
        'domain': DOMAIN,
        'label': 'Antenatal visit',
        'app_id': 'app',
        'app_build_id': 'build',
        'form_unique_id': 'form',
        'endpoint_id': 'endpoint',
        'session_type': 'survey',
        'allow_sms': False,
        'allow_email': True,
        'expires_at': timezone.now() + datetime.timedelta(days=30),
        **kwargs,
    })
