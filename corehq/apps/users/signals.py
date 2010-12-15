from __future__ import absolute_import
import logging
from datetime import datetime
from django.db.models.signals import post_save
from django.conf import settings
from django.contrib.auth.models import SiteProfileNotAvailable, User
from djangocouchuser.signals import couch_user_post_save
from couchforms.models import XFormInstance
from corehq.apps.receiver.signals import post_received
from corehq.apps.users.models import HqUserProfile, CouchUser

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
        # save updated django model data to couch model
        couch_user = profile.get_couch_user()
        for i in couch_user.django_user:
            couch_user.django_user[i] = getattr(instance, i)
        couch_user.save()
        
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
        from corehq.apps.users.models import create_hq_user_from_commcare_registration
        couch_user = create_hq_user_from_commcare_registration(domain, username, password, uuid, imei, date)
        
        return couch_user._id
    except Exception, e:
        #import traceback, sys
        #exc_type, exc_value, exc_traceback = sys.exc_info()
        #traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
        logging.error(str(e))
        raise

post_received.connect(create_user_from_commcare_registration)


"""
Case 3: 
This section automatically creates Couch users whenever a non-registration xform instance 
is received containing user data for a user that doesn't already exist
"""

def populate_user_from_commcare_submission(sender, xform, **kwargs):
    """
    Create a phone from a metadata submission if its a device we've
    not seen.
    """
    
    domain = xform.domain
    try:
        username = xform.form.Meta.username
        imei = xform.form.Meta.DeviceID
        
    except AttributeError:
        # if these fields don't exist, it's not a regular xform
        # so we just ignore it
        return
    
    matching_users = CouchUser.view("users/by_commcare_username_domain", key=[username, domain])
    num_matching_users = len(matching_users)
    user_already_exists = num_matching_users > 0
    if not user_already_exists:
        c = CouchUser()
        c.created_on = datetime.now()
        c.add_commcare_username(domain, username)
        c.add_phone_device(imei)
        c.status = 'auto_created'
        c.save()
    elif num_matching_users == 1:
        # user already exists. we should add SIM + IMEI info if applicable
        couch_user = matching_users.one()
        couch_user.add_phone_device(imei)
        couch_user.save()
    else:
        # >1 matching user. this is problematic.
        logging.error("Username %s in domain %s has multiple matches" % (username, domain)) 
    # we should also add phone and devices
    
post_received.connect(populate_user_from_commcare_submission)
