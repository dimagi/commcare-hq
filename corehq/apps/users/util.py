from django.conf import settings
from django.contrib.sites.models import Site
from dimagi.utils.couch.database import get_db
from django.contrib.auth.models import User

def format_username(username, domain):
    sitewide_domain = Site.objects.get(id = settings.SITE_ID).domain
    return "%s@%s.%s" % (username, domain, sitewide_domain)

def raw_username(username):
    """
    Strips the @domain.commcarehq.org from the username if it's there
    """
    return username.split("@")[0]

def django_user_from_couch_id(id):
    """
    From a couch id of a profile object, get the django user
    """
    # get the couch doc
    couch_rep = get_db().get(id)
    django_id = couch_rep["django_user"]["id"]
    return User.objects.get(id=django_id)

def commcare_account_from_django_user(django_user):
    couch_id = django_user.get_profile()._id
    from corehq.apps.users.models import CommCareAccount
    return CommCareAccount.view("users/commcare_users_by_login_id", 
                                key=couch_id).one()
    
                          
def couch_user_from_django_user(django_user):
    couch_id = django_user.get_profile()._id
    from corehq.apps.users.models import CouchUser
    return CouchUser.view("users/couch_users_by_django_profile_id", 
                          include_docs=True, key=couch_id).one()