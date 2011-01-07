"""
couch models go here
"""
from __future__ import absolute_import
from datetime import datetime
from django.contrib.auth.models import User
from django.db import models
from djangocouchuser.models import CouchUserProfile
from couchdbkit.ext.django.schema import *
from couchdbkit.schema.properties_proxy import SchemaListProperty
from djangocouch.utils import model_to_doc
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.users.util import django_user_from_couch_id,\
    couch_user_from_django_user
from dimagi.utils.mixins import UnicodeMixIn
import logging

COUCH_USER_AUTOCREATED_STATUS = 'autocreated'

class DomainMembership(Document):
    """
    Each user can have multiple accounts on the 
    web domain. This is primarily for Dimagi staff.
    """
    domain = StringProperty()
    permissions = StringListProperty()
    last_login = DateTimeProperty()
    date_joined = DateTimeProperty()
    
    class Meta:
        app_label = 'users'

class CommCareAccount(Document):
    """
    This is the information associated with a 
    particular commcare user. Right now, we 
    associate one commcare user to one web user
    (with multiple domain logins, phones, SIMS)
    but we could always extend to multiple commcare
    users if desired later.
    """
    django_user_id = StringProperty()
    UUID = StringProperty()
    registering_phone_id = StringProperty()
    user_data = DictProperty()
    domain = StringProperty()
    
    class Meta:
        app_label = 'users'

class PhoneDevice(Document):
    """
    This is a physical device with a unique IMEI
    Note, though, that the same physical device can 
    be used with multiple SIM cards (and multiple phone numbers)
    """
    is_default = BooleanProperty()
    IMEI = StringProperty()
    created = DateTimeProperty()
    
    class Meta:
        app_label = 'users'

class PhoneNumber(Document):
    """
    This is the SIM card with a unique phone number
    The same SIM card can be used in multiple phone
    devices
    """
    is_default = BooleanProperty()
    number = StringProperty()
    created = DateTimeProperty()
    
    class Meta:
        app_label = 'users'

class CouchUser(Document, UnicodeMixIn):
    """
    a user (for web+commcare+sms)
    can be associated with multiple usename/password/login tuples
    can be associated with multiple phone numbers/SIM cards
    can be associated with multiple phones/device IDs
    """
    # not used e.g. when user is only a commcare user
    django_user_id = StringProperty() # null = True
    domain_memberships = SchemaListProperty(DomainMembership)
    # the various commcare accounts associated with this user
    commcare_accounts = SchemaListProperty(CommCareAccount) 
    phone_devices = SchemaListProperty(PhoneDevice)
    phone_numbers = SchemaListProperty(PhoneNumber)
    created_on = DateTimeProperty()
    
    # these properties are associated with the main account.  
    # the account_id will defalult to the username of the first
    # linked django account 
    account_id = StringProperty()
    first_name = StringProperty()
    last_name = StringProperty()
    
    """
    For now, 'status' is things like:
        ('auto_created',     'Automatically created from form submission.'),   
        ('phone_registered', 'Registered from phone'),    
        ('site_edited',     'Manually added or edited from the HQ website.'),        
    """
    status = StringProperty()

    _user = None
    _user_checked = False

    class Meta:
        app_label = 'users'
    
    def __unicode__(self):
        return "couch user %s" % self.get_id
    
    @property
    def default_django_user(self):
        id = ""
        # first choice: web user login
        if self.django_user_id:       id = self.django_user_id 
        # second choice: latest registered commcare account
        elif self.commcare_accounts:  id = self.commcare_accounts[-1].django_user_id
        if not id:
            raise User.DoesNotExist("This couch user doesn't have a linked django account!")
        return django_user_from_couch_id(id)
            
    @property
    def username(self):
        return self.default_django_user.username
        
    def save(self, *args, **kwargs):
        # Call the "real" save() method.
        super(CouchUser, self).save(*args, **kwargs) 
    
    def delete(self, *args, **kwargs):
        try:
            django_user = self.get_django_user()
            django_user.delete()
        except User.DoesNotExist:
            pass
        super(CouchUser, self).delete(*args, **kwargs) # Call the "real" save() method.
    
    def add_django_user(self, username, password, **kwargs):
        # DO NOT implement this. It will create an endless loop.
        raise NotImplementedError

    def get_django_user(self): 
        return User.objects.get(username = self.django_user_id)

    def add_domain_membership(self, domain, **kwargs):
        for d in self.domain_memberships:
            if d.domain == domain:
                # membership already exists
                return
        self.domain_memberships.append(DomainMembership(domain = domain,
                                                        **kwargs))
    
    @property
    def domain_names(self):
        return [dm.domain for dm in self.domain_memberships]

    def get_active_domains(self):
        return Domain.objects.filter(name__in=self.domain_names)

    def is_member_of(self, domain_qs):
        membership_count = domain_qs.filter(name__in=self.domain_names).count()
        if membership_count > 0:
            return True
        return False
    
    def add_commcare_account(self, django_user, domain, uuid, imei, **kwargs):
        """
        Adds a commcare account to this. 
        """
        commcare_account = CommCareAccount(django_user_id=django_user.get_profile()._id,
                                           domain=domain,
                                           UUID=uuid, # todo: can we use a different uuid aka the actual id?
                                           registering_phone_id=imei,
                                           **kwargs)
        self.commcare_accounts.append(commcare_account)

    def link_commcare_account(self, domain, from_couch_user_id, commcare_username, **kwargs):
        from_couch_user = CouchUser.get(from_couch_user_id)
        for i in range(0, len(from_couch_user.commcare_accounts)):
            if from_couch_user.commcare_accounts[i].django_user.username == commcare_username:
                # this generates a 'document update conflict'. why?
                self.commcare_accounts.append(from_couch_user.commcare_accounts[i])
                self.save()
                del from_couch_user.commcare_accounts[i]
                from_couch_user.save()
                return
    
    def unlink_commcare_account(self, domain, commcare_user_index, **kwargs):
        commcare_user_index = int(commcare_user_index)
        c = CouchUser()
        c.created_on = datetime.now()
        original = self.commcare_accounts[commcare_user_index]
        c.commcare_accounts.append(original)
        c.status = 'unlinked from %s' % self._id
        c.save()
        # is there a more atomic way to do this?
        del self.commcare_accounts[commcare_user_index]
        self.save()
        
    def add_phone_device(self, IMEI, default=False, **kwargs):
        """ Don't add phone devices if they already exist """
        for device in self.phone_devices:
            if device.IMEI == IMEI:
                return
        self.phone_devices.append(PhoneDevice(IMEI=IMEI,
                                              default=default,
                                              **kwargs))
    
    def add_phone_number(self, number, default=False, **kwargs):
        """ Don't add phone numbers if they already exist """
        if not isinstance(number,basestring):
            number = str(number)
        for phone in self.phone_numbers:
            if phone.number == number:
                return
        self.phone_numbers.append(PhoneNumber(number=number,
                                              default=default,
                                              **kwargs))

    def get_phone_numbers(self):
        return [phone.number for phone in self.phone_numbers if phone.number]
    
    def default_phone_number(self):
        for phone_number in self.phone_numbers:
            if phone_number.is_default:
                return phone_number.number
        # if no default set, default to the last number added
        return self.phone_numbers[-1].number
    
    @property
    def couch_id(self):
        return self._id
    
    @classmethod
    def from_web_user(cls, user):
        couch_user = CouchUser()
        # TODO: fill in web properties
        couch_user.django_user_id = user.get_profile()._id
        couch_user.account_id = user.username
        couch_user.first_name = user.first_name
        couch_user.last_name = user.last_name
        return couch_user

class PhoneUser(Document):
    """A wrapper for response returned by phone_users_by_domain, etc."""
    id = StringProperty()
    name = StringProperty()
    phone_number = StringProperty()

"""
Django  models go here
"""

class HqUserProfile(CouchUserProfile):
    """
    The CoreHq Profile object, which saves the user data in couch along
    with annotating whatever additional fields we need for Hq
    (Right now, none additional are required)
    """
    
    class Meta:
        app_label = 'users'
    
    def __unicode__(self):
        return "%s" % (self.user)
        
    
def create_hq_user_from_commcare_registration_info(domain, username, password, uuid='', imei='', date='', **kwargs):
    """ na 'commcare user' is a couch user which:
    * does not have a web user
    * does have an associated commcare account,
        * has a django account linked to the commcare account for httpdigest auth
    """
    
    # create django user for the commcare account
    django_user = create_user(username, password, uuid=uuid)
    
    # create new couch user
    couch_user = CouchUser()
    couch_user.add_domain_membership(domain)
    
    # populate the couch user
    if not date:
        date = datetime.now()
    
    couch_user.add_commcare_account(django_user, domain, uuid, imei)
    couch_user.add_phone_device(IMEI=imei)
    # TODO: fix after clarifying desired behaviour
    # if 'user_data' in xform.form: couch_user.user_data = user_data
    couch_user.save()
    return couch_user
    

    
# make sure our signals are loaded
import corehq.apps.users.signals
