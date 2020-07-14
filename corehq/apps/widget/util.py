from corehq.apps.widget.models import DialerSettings


def domain_uses_dialer(domain):
    try:
        settings = DialerSettings.objects.get(domain=domain)
        return settings.is_enabled
    except DialerSettings.DoesNotExist:
        return False


def get_dialer_settings(domain):
    return DialerSettings.objects.get(domain=domain)
