def get_meta(request):
    return {
        'HTTP_X_FORWARDED_FOR': request.META.get('HTTP_X_FORWARDED_FOR'),
        'REMOTE_ADDR': request.META.get('REMOTE_ADDR'),
    }


def analytics_enabled_for_email(email_address):
    from corehq.apps.users.models import CouchUser
    user = CouchUser.get_by_username(email_address)
    return user.analytics_enabled if user else True
