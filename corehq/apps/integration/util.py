from corehq.apps.integration.models import (
    GaenOtpServerSettings,
)


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

    return context
