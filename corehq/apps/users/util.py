from django.conf import settings
from django.contrib.sites.models import Site
from dimagi.utils.couch.database import get_db
from django.contrib.auth.models import User

def format_username(username, domain):
    sitewide_domain = Site.objects.get(id = settings.SITE_ID).domain
    return "%s@%s.%s" % (username, domain, sitewide_domain)

def django_user_from_couch_id(id):
    """
    From a couch id of a profile object, get the django user
    """
    # get the couch doc
    couch_rep = get_db().get(id)
    django_id = couch_rep["django_user"]["id"]
    return User.objects.get(id=django_id)

