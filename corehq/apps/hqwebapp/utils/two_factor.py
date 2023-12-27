from django.conf import settings
from two_factor.plugins.registry import registry

from corehq.apps.hqwebapp.two_factor_methods import HQGeneratorMethod, HQPhoneCallMethod, HQSMSMethod


def user_can_use_phone(user):
    if not settings.ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE:
        return False

    return user.belongs_to_messaging_domain()


def register_two_factor_methods(user):
    """
    Registers custom two factor methods with HQ specific forms
    :param user: optional CouchUser object. If not specified, all methods will be registered
    """
    generator_method = registry.get_method('generator')
    if not isinstance(generator_method, HQGeneratorMethod):
        # the default generator method is registered when the registry is first created
        # so we should only need to unregister it once per django process
        registry.unregister('generator')
        registry.register(HQGeneratorMethod())

    if not user or user_can_use_phone(user):
        # default phone methods are registered when django starts which triggers register_methods
        # https://github.com/jazzband/django-two-factor-auth/blob/master/two_factor/plugins/phonenumber/apps.py#L19-L30
        if not isinstance(registry.get_method('call'), HQPhoneCallMethod):
            registry.unregister('call')
            registry.register(HQPhoneCallMethod())
        if not isinstance(registry.get_method('sms'), HQSMSMethod):
            registry.unregister('sms')
            registry.register(HQSMSMethod())
