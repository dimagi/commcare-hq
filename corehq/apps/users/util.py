from django.conf import settings
from django.contrib.sites.models import Site

def format_username(username, domain):
    sitewide_domain = Site.objects.get(id = settings.SITE_ID).domain
    return "%s@%s.%s" % (username, domain, sitewide_domain)

