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
        # the default generator method is registered when the registry first initialized
        # so we should only need to unregister it once for a view
        registry.unregister('generator')
        registry.register(HQGeneratorMethod())

    if not user or user_can_use_phone(user):
        registry.register(HQPhoneCallMethod())
        registry.register(HQSMSMethod())
