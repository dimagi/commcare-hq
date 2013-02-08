from django.conf import settings

RAVEN = bool(getattr(settings, 'SENTRY_DSN', None))

def base_template(request):
    """This sticks the base_template variable defined in the settings
       into the request context, so that we don't have to do it in 
       our render_to_response override."""

    return {
        'base_template': settings.BASE_TEMPLATE,
        'login_template': settings.LOGIN_TEMPLATE,
    }

def google_analytics(request):
    return {"GOOGLE_ANALYTICS_ID": settings.GOOGLE_ANALYTICS_ID}

def raven(request):
    """lets you know whether raven is being used"""
    return {
        'RAVEN': RAVEN
    }