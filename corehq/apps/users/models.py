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
from corehq.apps.users.util import django_user_from_couch_id

COUCH_USER_AUTOCREATED_STATUS = 'autocreated'

def _add_to_list(list, obj, default):
    if obj in list:
        list.remove(obj)
    if default:
        list.insert(0, obj)
    else:
        list.append(obj)
def _get_default(list):
    return list[0]

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

    # the UUID which is also the login doc's _id
    login_id = StringProperty()
    registering_device_id = StringProperty()
    user_data = DictProperty()
    domain = StringProperty()
    
    class Meta:
        app_label = 'users'


class WebAccount(Document):
    login_id = StringProperty() # null = True
    domain_memberships = SchemaListProperty(DomainMembership)
    
class CouchUser(Document):
    """
    a user (for web+commcare+sms)
    can be associated with multiple username/password/login tuples
    can be associated with multiple phone numbers/SIM cards
    can be associated with multiple phones/device IDs
    """
    # not used e.g. when user is only a commcare user

    first_name = StringProperty()
    last_name = StringProperty()
    email = StringProperty()

    # the various commcare accounts associated with this user
    web_account = SchemaProperty(WebAccount)
    commcare_accounts = SchemaListProperty(CommCareAccount)
    
    device_ids = ListProperty()
    phone_numbers = ListProperty()

    created_on = DateTimeProperty()
    
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
    
    @property
    def default_login(self):
        login_id = ""
        # first choice: web user login
        if self.login_id:
            login_id = self.web_account.login_id
        # second choice: latest registered commcare account
        elif self.commcare_accounts:
            login_id = _get_default(self.commcare_accounts).login_id
        else:
            raise User.DoesNotExist("This couch user doesn't have a linked django login!")
        return django_user_from_couch_id(login_id)
            
    @property
    def username(self):
        return self.default_login.username
        
    def save(self, *args, **kwargs):
        # Call the "real" save() method.
        super(CouchUser, self).save(*args, **kwargs) 
    
    def delete(self, *args, **kwargs):
        try:
            user = self.get_django_user()
            user.delete()
        except User.DoesNotExist:
            pass
        super(CouchUser, self).delete(*args, **kwargs) # Call the "real" save() method.
    
    def add_django_user(self, username, password, **kwargs):
        # DO NOT implement this. It will create an endless loop.
        raise NotImplementedError

    def get_django_user(self):
        return User.objects.get(username = self.web_account.login_id)

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
    
    def add_commcare_account(self, django_user, domain, device_id, **kwargs):
        """
        Adds a commcare account to this. 
        """
        commcare_account = CommCareAccount(login_id=django_user.get_profile()._id,
                                           domain=domain,
                                           registering_device_id=device_id,
                                           **kwargs)
        _add_to_list(self.commcare_accounts, commcare_account, default=True)

    def link_commcare_account(self, domain, from_couch_user_id, commcare_username, **kwargs):
        from_couch_user = CouchUser.get(from_couch_user_id)
        for i in range(0, len(from_couch_user.commcare_accounts)):
            if from_couch_user.commcare_accounts[i].login.username == commcare_username:
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
        
    def add_phone_device(self, device_id, default=False, **kwargs):
        """ Don't add phone devices if they already exist """
        _add_to_list(self.device_ids, device_id, default)
    
    def add_phone_number(self, phone_number, default=False, **kwargs):
        """ Don't add phone numbers if they already exist """
        if not isinstance(number,basestring):
            phone_number = str(phone_number)
        _add_to_list(self.phone_numbers, phone_number, default)
    
    def default_phone_number(self):
        return _get_default(self.phone_numbers)
    
    @property
    def couch_id(self):
        return self._id

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
        
    def get_couch_user(self):
        # This caching could be useful, but for now we leave it out since
        # we don't yet have a good intelligent refresh mechanism
        # def get_couch_user(self, force_update=False):
        #if not hasattr(self,'couch_user') or force_update:
        #    self.couch_user = CouchUser.get(self._id)
        #return self.couch_user
        return CouchUser.get(self._id)
    

def create_hq_user_from_commcare_registration_info(domain, username, password, uuid='', device_id='', date='', **kwargs):
    """ na 'commcare user' is a couch user which:
    * does not have a web user
    * does have an associated commcare account,
        * has a django account linked to the commcare account for httpdigest auth
    """
    # create django user for the commcare account
    login = create_user(username, password, uuid=uuid)
    
    # create new couch user
    couch_user = new_couch_user(domain)
    # populate the couch user
    if not date:
        date = datetime.now()
    
    couch_user.add_commcare_account(login, domain, uuid, device_id)
    couch_user.add_phone_device(device_id=device_id)
    # TODO: fix after clarifying desired behaviour
    # if 'user_data' in xform.form: couch_user.user_data = user_data
    couch_user.save()
    return couch_user
    

def new_couch_user(domain):
    """
    Gets a new couch user in a domain. 
    """
    couch_user = CouchUser()
    # add metadata to couch user
    couch_user.add_domain_membership(domain)
    return couch_user
    
    
# make sure our signals are loaded
import corehq.apps.users.signals
