from corehq.apps.integration.models import (
    DialerSettings,
    GaenOtpServerSettings,
)


def domain_uses_dialer(domain):
    try:
        settings = DialerSettings.objects.get(domain=domain)
        return settings.is_enabled
    except DialerSettings.DoesNotExist:
        return False


def get_gaen_otp_server_settings(domain):
    try:
        settings = GaenOtpServerSettings.objects.get(domain=domain)
        return settings if settings.is_enabled else None
    except GaenOtpServerSettings.DoesNotExist:
        pass


def get_dialer_settings(domain):
    return DialerSettings.objects.get(domain=domain)


def integration_contexts(domain):
    context = {'dialer_enabled': domain_uses_dialer(domain)}

    gaen_otp_server_settings = get_gaen_otp_server_settings(domain)
    if gaen_otp_server_settings:
        context.update({
            'gaen_otp_enabled': True
        })

    return context
