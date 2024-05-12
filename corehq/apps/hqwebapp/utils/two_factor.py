from django.conf import settings


def user_can_use_phone(user):
    if not settings.ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE:
        return False

    return user.belongs_to_messaging_domain()
