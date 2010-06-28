from __future__ import absolute_import
import datetime, time

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from domain.models import Membership
from phone.models import Phone, PhoneUserInfo
# this import is silly and the referenced method should be moved to a shared utility location
from xformmanager.util import get_unique_value
from xml.etree import ElementTree


USERNAME_TAG = "username"
PASSWORD_TAG = "password"
UUID_TAG = "uuid"
REGISTERING_PHONE_ID_TAG = "registering_phone_id"
DATE_TAG = "date"
ADDITIONAL_DATA_TAG = "user_data"

BASIC_TAGS = [USERNAME_TAG, PASSWORD_TAG, UUID_TAG, REGISTERING_PHONE_ID_TAG, DATE_TAG]

class Registration(object):
    """Registration information, processed from XML"""
    
    def __init__(self, attachment):
        # this comes in as xml that looks like:
        # <n0:registration xmlns:n0="openrosa.org/user-registration">
        # <username>user</username>
        # <password>pw</password>
        # <uuid>MTBZJTDO3SCT2ONXAQ88WM0CH</uuid>
        # <date>2008-01-07</date>
        # <registering_phone_id>NRPHIOUSVEA215AJL8FFKGTVR</registering_phone_id>
        # <user_data> ... some custom stuff </user_data>
        self.domain = attachment.submission.domain
        
        xml_payload = attachment.get_contents()
        
        # TODO: smarter (more library-based) xml-processing
        element = ElementTree.XML(xml_payload)
        
        for basic_tag in BASIC_TAGS:   setattr(self, basic_tag, None)
        for child in element:
            if child.tag in BASIC_TAGS:
                setattr(self, child.tag, child.text)
            elif child.tag == ADDITIONAL_DATA_TAG:
                self.additional_data = {}
                for generic_data in child:
                    self.additional_data[generic_data.items()[0][1]] = generic_data.text
        
        if self.date:
            # the expected format is "2010-03-23"
            # self.date = \
            #    datetime.datetime.strptime(self.date, "%Y-%m-%d").date()
            pass
            
@transaction.commit_on_success
def create_registration_objects(attachment):
    reg = Registration(attachment)
    # we make these django users for future authentication purposes
    # and generic 'user grouping' functionality
    phone = Phone.objects.get_or_create(device_id=reg.registering_phone_id,
                                        domain=reg.domain)[0]
    try:
        phone_info = PhoneUserInfo.objects.get(phone=phone, username=reg.username)
        if phone_info.status == "phone_created":
            raise Exception("Tried to register user %s on phone %s but was already registered!" % \
                            (reg.username, phone.device_id))
    except PhoneUserInfo.DoesNotExist:
        # fine, we are just creating a new one
        phone_info = PhoneUserInfo()
    
    phone_info.phone = phone
    phone_info.attachment = attachment
    phone_info.status = "phone_registered"
    phone_info.username = reg.username
    phone_info.password = reg.password
    phone_info.uuid = reg.uuid
    phone_info.registered_on = reg.date
    phone_info.additional_data = reg.additional_data
    if not phone_info.user:
        # since we don't have a good way to look who this is up based on what 
        # comes in from the phone, assume that we always want to create a new user.  
        phone_info.user = create_django_user_and_domain_membership(phone_info)
    phone_info.save()
    
def create_django_user_and_domain_membership(phone_info):
    """
    From a phone info object, automatically get a django user object
    """
    
    user = get_django_user_object(phone_info)
    user.save()
    
    # add to the domain too
    phone_info.phone.domain.add(user)
    return user

def get_django_user_object(phone_info):
    """From a PhoneUserInfo object, automatically build a django user"""
    user = User()
    user.username = get_unique_value(User.objects, "username", phone_info.username, "")
    user.set_password(phone_info.password)
    user.first_name = ''
    user.last_name  = ''
    user.email = ""
    user.is_staff = False # Can't log in to admin site
    user.is_active = True # Activated upon receipt of confirmation
    user.is_superuser = False # Certainly not, although this makes login sad
    user.last_login =  datetime.datetime(1970,1,1)
    user.date_joined = datetime.datetime.utcnow()
    return user