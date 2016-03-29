from datetime import date, timedelta
from corehq.apps.es import UserES
from corehq.apps.users.models import WebUser

def get_meta(request):
    return {
        'HTTP_X_FORWARDED_FOR': request.META.get('HTTP_X_FORWARDED_FOR'),
        'REMOTE_ADDR': request.META.get('REMOTE_ADDR'),
    }

def get_active_users():
    six_months_ago = date.today() - timedelta(days=180)
    users = UserES().web_users().last_logged_in(gte=six_months_ago).run().hits
    return (WebUser.wrap(u) for u in users)