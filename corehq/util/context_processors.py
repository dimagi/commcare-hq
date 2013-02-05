from django.conf import settings
import sys

def base_template(request):
    """This sticks the base_template variable defined in the settings
       into the request context."""

    return {
        'base_template': settings.BASE_TEMPLATE,
        'login_template': settings.LOGIN_TEMPLATE,
    }

def google_analytics(request):
    return {"GOOGLE_ANALYTICS_ID": settings.GOOGLE_ANALYTICS_ID}
