import hashlib

from corehq.apps.integration.models import (
    GaenOtpServerSettings,
    HmacCalloutSettings,
)


def get_hmac_callout_settings(domain):
    try:
        settings = HmacCalloutSettings.objects.get(domain=domain)
        return settings if settings.is_enabled else None
    except HmacCalloutSettings.DoesNotExist:
        pass


def get_gaen_otp_server_settings(domain):
    try:
        settings = GaenOtpServerSettings.objects.get(domain=domain)
        return settings if settings.is_enabled else None
    except GaenOtpServerSettings.DoesNotExist:
        pass


def integration_contexts(domain):
    context = {}
    gaen_otp_server_settings = get_gaen_otp_server_settings(domain)
    if gaen_otp_server_settings:
        context.update({
            'gaen_otp_enabled': True
        })

    hmac_settings = get_hmac_callout_settings(domain)
    if hmac_settings:
        context.update({
            'hmac_root_url': hmac_settings.destination_url,
            'hmac_api_key': hmac_settings.api_key,
            'hmac_hashed_secret': hash_secret(hmac_settings.api_secret),
        })

    return context


def hash_secret(secret):
    return hashlib.sha512(secret.encode()).hexdigest()
