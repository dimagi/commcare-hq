from __future__ import absolute_import
import logging
from django.core.exceptions import ValidationError
import corehq.apps.users.xml as xml
from datetime import datetime
from django.db.models.signals import post_save
from django.conf import settings
from django.contrib.auth.models import SiteProfileNotAvailable, User
from djangocouchuser.signals import couch_user_post_save
from couchforms.models import XFormInstance
from receiver.signals import successful_form_received, ReceiverResult,\
    Certainty
from corehq.apps.users.models import HqUserProfile, CouchUser, COUCH_USER_AUTOCREATED_STATUS,\
    create_hq_user_from_commcare_registration_info
from dimagi.utils.django.database import get_unique_value
from corehq.apps.users.util import format_username, django_user_from_couch_id,\
    couch_user_from_django_user, normalize_username
from dimagi.utils.logging import log_exception
from couchdbkit.resource import ResourceNotFound

# xmlns that registrations and backups come in as, respectively. 
REGISTRATION_XMLNS = "http://openrosa.org/user-registration"

"""
Case 1: 
This section automatically creates profile documents in couch 
whenever a web user is created
"""
def create_profile_from_django_user(sender, instance, created, **kwargs): 
    """
    The user post save signal, to auto-create our Profile
    """
    def _update_couch_username(user):
        profile = user.get_profile()
        couch_user = profile.get_couch_user()
        if couch_user:
            default_account = couch_user.default_account
            if default_account and default_account.login_id == profile._id \
               and couch_user._doc.get("username") != user.username:
                # this is super hacky but the only way to set the property
                couch_user._doc["username"] = instance.username
                couch_user.save()
    
    if not created:
        try:
            instance.get_profile().save()
            _update_couch_username(instance)
            return
        except HqUserProfile.DoesNotExist:
            logging.warn("There should have been a profile for "
                         "%s but wasn't.  Creating one now." % instance)
        except SiteProfileNotAvailable:
            raise
    if hasattr(instance, 'uuid'):
        try:
            profile = HqUserProfile.objects.get(_id=instance.uuid)
            if profile.user != instance:
                raise Exception("You can't have profiles for different users with the same guid!")
        except HqUserProfile.DoesNotExist:
            profile = HqUserProfile.objects.create(_id=instance.uuid, user=instance)
    else:
        profile, created = HqUserProfile.objects.get_or_create(user=instance)

    if not created:
        # magically calls our other save signal
        profile.save()
        
    # finally update the CouchUser doc, if necessary
    _update_couch_username(instance)
    
post_save.connect(create_profile_from_django_user, User)        
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
        domain = xform.domain
        def user_data_from_reg_form(xform):
            ret = {}
            if "user_data" in xform.form and "data" in xform.form["user_data"]:
                vals = xform.form["user_data"]["data"]
                if not isinstance(vals, list):
                    vals = [vals]
                for item in vals:
                    # this is ugly, but how the data comes in
                    ret[item["@key"]] = item["#text"]
            return ret
        user_data = user_data_from_reg_form(xform)
        
        # check for uuid conflicts
        django = None
        try:
            django = django_user_from_couch_id(uuid)
            logging.error("Trying to create a new user %s from form %s!  Currently you can't submit multiple registration xmls for the same uuid." % \
                          (uuid, xform.get_id))
            # this will just respond back with whatever was in the first
            # registration xml packet.
            return ReceiverResult(xml.get_response(couch_user_from_django_user(django)), Certainty.CERTAIN)
            
        except ResourceNotFound, e: pass
        except User.DoesNotExist:   pass
        # we need to check for username conflicts, other issues
        # and make sure we send the appropriate conflict response to the
        # phone.
        try:
            username = normalize_username(username, domain)
        except ValidationError:
            raise Exception("Username (%s) is invalid: valid characters include [a-z], "
                            "[0-9], period, underscore, and single quote" % username)
        try: 
            User.objects.get(username=username)
            prefix, suffix = username.split("@") 
            username = get_unique_value(User.objects, "username", prefix, sep="", suffix="@%s" % suffix)
        except User.DoesNotExist:
            # they didn't exist, so we can use this username
            pass
        
        
        couch_user = create_hq_user_from_commcare_registration_info(domain, username, password, 
                                                                    uuid, imei, date, user_data)
        return ReceiverResult(xml.get_response(couch_user), Certainty.CERTAIN)
    except Exception, e:
        #import traceback, sys
        #exc_type, exc_value, exc_traceback = sys.exc_info()
        #traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
        logging.exception(e)
        raise

successful_form_received.connect(create_user_from_commcare_registration)