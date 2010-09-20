from __future__ import absolute_import
from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save

from corehq.apps.domain.models import Domain
from corehq.apps.phone.processor import create_backup, create_phone_user, BACKUP_XMLNS, \
    REGISTRATION_XMLNS
#from corehq.apps.receiver.models import Attachment

from corehq.util.djangoplus.fields import PickledObjectField
from couchforms.models import Metadata
#import corehq.apps.xforms.xmlrouter as xmlrouter

class Phone(models.Model):
    """A phone (device)."""
    device_id = models.CharField(max_length=32)
    domain = models.ForeignKey(Domain, related_name="phones")
    
    def __unicode__(self):
        return self.device_id
    

USER_INFO_STATUS = (    
    ('auto_created',     'Automatically created from form submission.'),   
    ('phone_registered', 'Registered from corehq.apps.phone'),    
    ('site_edited',     'Manually added or edited from the HQ website.'),    
)

class PhoneUserInfo(models.Model):
    """
    Someone who uses a phone.  This object is somewhat like a profile in that 
    it basically annotates a User account with some extra info about the phone
    the user is using.  However a user might have multiple phones.
    """
    user = models.ForeignKey(User, null=True, related_name="phone_registrations")
    phone = models.ForeignKey(Phone, related_name="users")
    
#    attachment = models.OneToOneField(Attachment, null=True)
    
    status = models.CharField(max_length=20, choices=USER_INFO_STATUS)
    
    # the username and password are from the phone, not the user account
    username = models.CharField(max_length=32)
    password = models.CharField(max_length=32, null=True) 
    uuid = models.CharField(max_length=32, null=True)
    registered_on = models.DateField(default=datetime.today)
    additional_data = models.TextField(null=True, blank=True)
    
    class Meta:
        unique_together = ("phone", "username")

    def __unicode__(self):
        # prefix = "(%s)"  % self.user if self.user else "Unregistered user"
        return "%s on phone %s" % (self.username, self.phone) 
        
    
    
class PhoneBackup(models.Model):
    """An instance of a phone backup.  Points to a specific device
       as well as a set of users.  Additionally, has information about
       the original attachment that created the backup"""
    
    # TODO: Should this  be moved to its own app since it's not core
    # phone user functionality?
#    attachment = models.ForeignKey(Attachment)
    phone = models.ForeignKey(Phone)

    def __unicode__(self):
        return "Id: %s, Device: %s, Users: %s" % (self.id, self.phone,
                                                  self.device.users.count())


def create_phone_and_user(sender, instance, created, **kwargs):
    """
    Create a phone from a metadata submission if its a device we've
    not seen.
    """
    
    if not created:             return
    if not instance.deviceid:   return
    
    phone = Phone.objects.get_or_create\
                (device_id = instance.deviceid,
                 domain = instance.attachment.submission.domain)[0]


    try:
        # simple lookup
        PhoneUserInfo.objects.get(phone=phone, username=instance.username)
    except PhoneUserInfo.DoesNotExist:
        try:
            # perhaps by UUID then?
            PhoneUserInfo.objects.get(uuid=instance.chw_id)
        except PhoneUserInfo.DoesNotExist:
            # definitely not there
            PhoneUserInfo.objects.create(phone=phone,username=instance.username,
                                         status="auto_created")

post_save.connect(create_phone_and_user, sender=Metadata)
    
# register our backup and registration methods, like a signal, 
# in the models file to make sure this always gets bootstrapped.
#xmlrouter.register(BACKUP_XMLNS, create_backup)
#xmlrouter.register(REGISTRATION_XMLNS, create_phone_user)
