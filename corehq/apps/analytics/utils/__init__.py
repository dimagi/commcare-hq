import json
import requests
import logging

from django.conf import settings

logger = logging.getLogger('analytics')
logger.setLevel('DEBUG')


def get_meta(request):
    return {
        'HTTP_X_FORWARDED_FOR': request.META.get('HTTP_X_FORWARDED_FOR'),
        'REMOTE_ADDR': request.META.get('REMOTE_ADDR'),
    }


def analytics_enabled_for_email(email_address):
    from corehq.apps.users.models import CouchUser
    user = CouchUser.get_by_username(email_address)
    return user.analytics_enabled if user else True


def get_instance_string():
    instance = settings.ANALYTICS_CONFIG.get('HQ_INSTANCE', '')
    env = '' if instance == 'www' else instance + '_'
    return env


def get_client_ip_from_request(request):
    meta = get_meta(request)
    return get_client_ip_from_meta(meta)


def get_client_ip_from_meta(meta):
    x_forwarded_for = meta.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = meta.get('REMOTE_ADDR')
    return ip


def log_response(target, data, response):
    status_code = response.status_code if isinstance(response, requests.models.Response) else response.status
    try:
        response_text = json.dumps(response.json(), indent=2, sort_keys=True)
    except Exception:
        response_text = status_code

    message = 'Sent this data to {target}: {data} \nreceived: {response}'.format(
        target=target,
        data=json.dumps(data, indent=2, sort_keys=True),
        response=response_text
    )

    if 400 <= status_code < 600:
        logger.error(message)
    else:
        logger.debug(message)
