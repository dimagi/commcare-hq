from django.apps import AppConfig
from django.conf import settings

from two_factor.plugins.registry import registry


class HqWebAppConfig(AppConfig):
    name = 'corehq.apps.hqwebapp'

    def ready(self):
        # Ensure the login signal handlers have been loaded
        from . import login_handlers, signals  # noqa

        # custom 2FA methods need to be registered on startup
        register_two_factor_methods()


def register_two_factor_methods():
    from corehq.apps.hqwebapp.two_factor_methods import (
        HQGeneratorMethod,
        HQPhoneCallMethod,
        HQSMSMethod,
    )

    # default generator method is registered when the registry object is created
    # https://github.com/jazzband/django-two-factor-auth/blob/1.15.5/two_factor/plugins/registry.py#L76-L77
    registry.unregister('generator')
    registry.register(HQGeneratorMethod())

    # default phone methods are registered when django starts up
    # https://github.com/jazzband/django-two-factor-auth/blob/1.15.5/two_factor/plugins/phonenumber/apps.py#L19-L30
    if not settings.ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE:
        registry.unregister('call')
        registry.unregister('sms')
        return

    if getattr(settings, 'TWO_FACTOR_CALL_GATEWAY', None):
        registry.unregister('call')
        registry.register(HQPhoneCallMethod())

    if getattr(settings, 'TWO_FACTOR_SMS_GATEWAY', None):
        registry.unregister('sms')
        registry.register(HQSMSMethod())
