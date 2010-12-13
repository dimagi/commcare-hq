"""
couch models go here
"""
from __future__ import absolute_import
import datetime
from django.contrib.auth.models import User
from django.db import models
from djangocouchuser.models import CouchUserProfile
from couchdbkit.ext.django.schema import *
from couchdbkit.schema.properties_proxy import SchemaListProperty
from djangocouch.utils import model_to_doc

class DjangoUser(Document):
    id = IntegerProperty()
    username = StringProperty()
    first_name = StringProperty()
    last_name = StringProperty()
    django_type = StringProperty()
    is_active = BooleanProperty()
    email = StringProperty()
    is_superuser = BooleanProperty()
    is_staff = BooleanProperty()
    last_login = DateTimeProperty()
    groups = ListProperty()
    user_permissions = ListProperty()
    password = StringProperty()
    date_joined = DateTimeProperty()
        
    class Meta:
        app_label = 'users'

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
    django_user = SchemaProperty(DjangoUser)
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

class CouchUser(Document):
    """
    a user (for web+commcare+sms)
    can be associated with multiple usename/password/login tuples
    can be associated with multiple phone numbers/SIM cards
    can be associated with multiple phones/device IDs
    """
    django_user = SchemaProperty(DjangoUser)
    domain_memberships = SchemaListProperty(DomainMembership)
    commcare_accounts = SchemaListProperty(CommCareAccount)
    phone_devices = SchemaListProperty(PhoneDevice)
    phone_numbers = SchemaListProperty(PhoneNumber)
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
        
    def save(self, *args, **kwargs):
        self.django_type = "users.hquserprofile"
        super(CouchUser, self).save(*args, **kwargs) # Call the "real" save() method.
    
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
        return User.objects.get(id = self.django_user.id)

    def add_domain_membership(self, domain, **kwargs):
        for d in self.domain_memberships:
            if d.domain == domain:
                # membership already exists
                return
        self.domain_memberships.append(DomainMembership(domain = domain,
                                                        **kwargs))

    def create_commcare_user(self, domain, username, password, uuid='', imei='', date='', **kwargs):
        def _create_django_user_from_registration_data(domain, username, password):
            """ 
            From registration xml data, automatically build a django user
            Note that we set the 'is_commcare_user' flag here, so that we don't
            auto-generate the couch user
            """
            user = User()
            user.username = username
            user.set_password(password)
            user.first_name = ''
            user.domain = domain
            user.last_name  = ''
            user.email = ""
            user.is_staff = False # Can't log in to admin site
            user.is_active = True # Activated upon receipt of confirmation
            user.is_superuser = False # Certainly not, although this makes login sad
            user.last_login =  datetime.datetime(1970,1,1)
            user.date_joined = datetime.datetime.utcnow()
            user.is_commcare_user = True
            return user
        def _add_commcare_account(django_user, domain, UUID, registering_phone_id, **kwargs):
            """ 
            This function expects a real django user.
            Note that it doesn't create a django user.
            """
            for commcare_account in self.commcare_accounts:
                if commcare_account.django_user.id == django_user.id  and \
                   commcare_account.domain == domain and \
                   commcare_account.UUID == UUID and \
                   commcare_account.registering_phone_id == registering_phone_id:
                        # already exists
                        return
            django_user_doc = model_to_doc(django_user)
            commcare_account = CommCareAccount(django_user=django_user_doc,
                                               domain=domain,
                                               UUID=UUID,
                                               registering_phone_id=registering_phone_id,
                                               **kwargs)
            self.commcare_accounts.append(commcare_account)
        django_user = _create_django_user_from_registration_data(domain, username, password)        
        django_user.save()
        _add_commcare_account(django_user, domain, uuid, imei, date_registered = date, **kwargs)

    def add_commcare_username(self, domain, username, **kwargs):
        """
        This function doesn't set up a full commcare account, it only  has the username
        This is placeholder, used when we receive xforms from a user who hasn't registered
        and so for whom we don't have a password. This needs to be manually linked to
        a commcare/django account asap.
        """
        django_user = DjangoUser(username=username)
        for commcare_account in self.commcare_accounts:
            if commcare_account.domain == domain and commcare_account.django_user.username == username:
                return
        commcare_account = CommCareAccount(django_user=django_user,
                                           domain=domain,
                                           **kwargs)
        self.commcare_accounts.append(commcare_account)
       
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
        for phone in self.phone_numbers:
            if phone.number == number:
                return
        self.phone_numbers.append(PhoneNumber(number=number,
                                              default=default,
                                              **kwargs))

    def get_phone_numbers(self):
        return [phone.number for phone in self.phone_numbers]
    
    @property
    def couch_id(self):
        return self._id




"""
Django  models go here
"""

class HqUserProfile(CouchUserProfile):
    """
    The CoreHq Profile object, which saves the user data in couch along
    with annotating whatever additional fields we need for Hq
    (Right now, none additional are required)
    """
    is_commcare_user = models.BooleanField(default=False)

    class Meta:
        app_label = 'users'
    
    def __unicode__(self):
        return "%s @ %s" % (self.user)

    def get_couch_user(self):
        couch_user = CouchUser.get(self._id)
        return couch_user


def create_hq_user_from_commcare_registration(domain, username, password, uuid='', imei='', date='', **kwargs):
#def create_commcare_user(domain, username, password, uuid='', imei='', date='', **kwargs):
    """ a 'commcare user' is a couch user which:
    * has a django web login  
    * has an associated commcare account,
        * has a second django account linked to the commcare account for httpdigest auth
    """
    num_couch_users = len(CouchUser.view("users/by_username_domain", 
                                         key=[username, domain]))
    # TODO: add a check for when uuid is not unique
    couch_user = CouchUser()
    if num_couch_users > 0:
        couch_user.is_duplicate = "True"
        couch_user.save()
    # add metadata to couch user
    couch_user.add_domain_membership(domain)
    couch_user.create_commcare_user(domain, username, password, uuid, imei, date)
    couch_user.add_phone_device(IMEI=imei)
    # TODO: fix after clarifying desired behaviour
    # if 'user_data' in xform.form: couch_user.user_data = user_data
    couch_user.save()
    return couch_user

# make sure our signals are loaded
import corehq.apps.users.signals