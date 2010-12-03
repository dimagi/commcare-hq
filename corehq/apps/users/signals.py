from __future__ import absolute_import
import logging
from django.db.models.signals import post_save
from django.conf import settings
from django.contrib.auth.models import SiteProfileNotAvailable, User
from djangocouchuser.signals import couch_user_post_save
from corehq.apps.users.models import HqUserProfile, CouchUser
from corehq.apps.users.models.django import create_django_user_from_registration_data
from corehq.apps.receiver.signals import post_received
from couchforms.models import XFormInstance

# xmlns that registrations and backups come in as, respectively. 
REGISTRATION_XMLNS = "http://openrosa.org/user-registration"

"""
Case 1: 
This section automatically creates Couch users whenever a web user is created
"""
def create_user_from_django_user(sender, instance, created, **kwargs): 
    """
    The user post save signal, to auto-create our Profile
    """
    if not created:
        try:
            instance.get_profile().save()
            return
        except HqUserProfile.DoesNotExist:
            logging.warn("There should have been a profile for "
                         "%s but wasn't.  Creating one now." % instance)
        except SiteProfileNotAvailable:
            raise
    
    if hasattr(instance, 'is_commcare_user'):
        profile, created = HqUserProfile.objects.get_or_create(user=instance, is_commcare_user=instance.is_commcare_user)
    else:
        profile, created = HqUserProfile.objects.get_or_create(user=instance)

    if not created:
        # magically calls our other save signal
        profile.save()
        
post_save.connect(create_user_from_django_user, User)        
post_save.connect(couch_user_post_save, HqUserProfile)

"""
Case 2: 
This section automatically creates Couch users whenever a registration xform is received

Question: is it possible to receive registration data from the phone after Case 3?
If so, we need to check for a user created via Case 3 and link them to this account
automatically
"""

def create_user_from_commcare_registration(sender, xform, **kwargs):
    """
    # this comes in as xml that looks like:
    # <n0:registration xmlns:n0="openrosa.org/user-registration">
    # <username>user</username>
    # <password>pw</password>
    # <uuid>MTBZJTDO3SCT2ONXAQ88WM0CH</uuid>
    # <date>2008-01-07</date>
    # <registering_phone_id>NRPHIOUSVEA215AJL8FFKGTVR</registering_phone_id>
    # <user_data> ... some custom stuff </user_data>
    """
    try:
        if xform.xmlns != REGISTRATION_XMLNS:
            return False
        if not ('username' in xform.form and 
                'password' in xform.form and 
                'uuid' in xform.form and 
                'date' in xform.form and 
                'registering_phone_id' in xform.form):
                    raise Exception("Poorly configured registration XML")
        username = xform.form['username']
        password = xform.form['password']
        uuid = xform.form['uuid']
        date = xform.form['date']
        imei = xform.form['registering_phone_id']
        # TODO: implement this properly, more like xml_to_json(user_data)
        domain = xform.domain
        num_couch_users = len(CouchUser.view("users/by_username_password", 
                                             key=[username, password, domain]))
        user = User(username=username, 
                    password=password)
        # TODO: add a check for when uuid is not unique
        user.save()
        couch_user = user.get_profile().get_couch_user()
        if num_couch_users > 0:
            couch_user.is_duplicate = "True"
            couch_user.save()
        # add metadata to couch user
        couch_user.add_domain_membership(domain)
        django_user = create_django_user_from_registration_data(username, password)
        django_user.save()
        couch_user.add_commcare_account(django_user, domain, uuid, imei, date_registered = date, **kwargs)
        couch_user.add_phone_device(IMEI=imei)
        # TODO: fix after clarifying desired behaviour
        # if 'user_data' in xform.form: couch_user.user_data = user_data
        couch_user.save()
        return couch_user._id
    except Exception, e:
        #import traceback, sys
        #exc_type, exc_value, exc_traceback = sys.exc_info()
        #traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
        logging.error(str(e))
        raise

post_received.connect(create_user_from_commcare_registration)
