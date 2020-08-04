import uuid
import hashlib

from corehq.apps.integration.models import DialerSettings, HmacCalloutSettings


def domain_uses_dialer(domain):
    try:
        settings = DialerSettings.objects.get(domain=domain)
        return settings.is_enabled
    except DialerSettings.DoesNotExist:
        return False

def domain_uses_hmac_callout(domain):
    try:
        settings = HmacCalloutSettings.objects.get(domain=domain)
        return settings.is_enabled
    except HmacCalloutSettings.DoesNotExist:
        return False

def get_dialer_settings(domain):
    return DialerSettings.objects.get(domain=domain)

def integration_contexts(domain):
    context = {'dialer_enabled': domain_uses_dialer(domain)}
    if domain_uses_hmac_callout:
        settings = HmacCalloutSettings.objects.get(domain=domain)
        context.update({
            'hmac_root_url': settings.destination_url,
            'hmac_api_key': settings.api_key,
            'hmac_hashed_secret': hash_secret(settings.api_secret),
            })

    return context
 
def hash_secret(secret):
    return hashlib.sha256(secret.encode()).hexdigest()
