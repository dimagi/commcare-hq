from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db import models
from domain import Permissions

##############################################################################################################
#
# Originally had my own hacky global storage of content type, but it turns out that contenttype.models
# wisely caches content types! No hit to the db beyond the first call - no need for us to do our own 
# custom caching.
#
# See ContentType.get_for_model() code for details.

class Domain(models.Model):
    '''Domain is the highest level collection of people/stuff
       in the system.  Pretty much everything happens at the 
       domain-level, including user membership, permission to 
       see data, reports, charts, etc.'''
       
    
    name  = models.CharField(max_length = 64, unique=True)
    is_active = models.BooleanField(default=False)
    #description = models.CharField(max_length=255, null=True, blank=True)
    #timezone = models.CharField(max_length=64,null=True)
    
    # Utility function - gets active domains in which user has an active membership 
    # Note that User.is_active is not checked here - we're only concerned about usable
    # domains in which the user can theoretically participate, not whether the user 
    # is cleared to login. 
    @staticmethod
    def active_for_user(user):            
        return Domain.objects.filter( membership__member_type = ContentType.objects.get_for_model(User), 
                                      membership__member_id = user.id, 
                                      membership__is_active=True, # Looks in membership table
                                      is_active=True) # Looks in domain table
                
    def __unicode__(self):
        return self.name

##############################################################################################################
#
# Use cases:
#
# Get all members in a domain:
# Member.objects.filter(member_type = 3, domain = 1) then iterate - slow, because of one query (for User) per row
# User.objects.filter(membership__domain = 2) - fast, but requires the addition of a GenericRelation to User. 
# See UserInDomain, below.
#
# Get all domains to which a member belongs:
# User.objects.get(id = 1).membership.all() and then iterate to pick out domains - slow, because of one query 
#       (for Domain) per row. Requires GenericRelation on User.
# Member.objects.filter(member_type = 3, member_id = 1).query.as_sql()   Generate same SQL, and require same 
#       slow iteration
# Domain.objects.filter(membership__member_type = 3, membership__member_id = 1) - fast, and requires no new fields
#       (as Domain is a FK of Member)
#

member_limits = {'model__in':('user', 'formdatagroup')}
                                         
class Membership(models.Model):
    domain = models.ForeignKey(Domain)
    member_type = models.ForeignKey(ContentType, limit_choices_to=member_limits)
    member_id = models.PositiveIntegerField()
    member_object = generic.GenericForeignKey('member_type', 'member_id')
    is_active = models.BooleanField(default=False)

    def __unicode__(self):
        return str(self.member_type) + str(self.member_id) + str(self.member_object)

##############################################################################################################

class RegistrationRequest(models.Model):
    tos_confirmed = models.BooleanField(default=False)
    # No verbose name on times and IPs - filled in on server
    request_time = models.DateTimeField() 
    request_ip = models.IPAddressField()
    activation_guid = models.CharField(max_length=32, unique=True)
    # confirm info is blank until a confirming click is received
    confirm_time = models.DateTimeField(null=True, blank=True)
    confirm_ip = models.IPAddressField(null=True, blank=True) 
    domain = models.OneToOneField(Domain) 
    new_user = models.ForeignKey(User, related_name='new_user') # Not clear if we'll always create a new user - might be many reqs to one user, thus FK 
    # requesting_user is only filled in if a logged-in user requests a domain. 
    requesting_user = models.ForeignKey(User, related_name='requesting_user', null=True, blank=True) # blank and null -> FK is optional.
    
    class Meta:
        db_table = 'domain_registration_request'

# To be added:    
# language
# number pref
# currency pref
# date pref
# time pref    

##############################################################################################################

class Settings(models.Model):
    domain = models.OneToOneField(Domain)
    max_users = models.PositiveIntegerField()
    
# To be added - all of the date, time, etc. fields that will go into RegistrationRequest

##############################################################################################################
#
# http://bolhoed.net/blog/how-to-dynamically-add-fields-to-a-django-model shows:
#
# User.add_to_class('membership', generic.GenericRelation(Membership, content_type_field='member_type', object_id_field='member_id'))
#
# Rather than that hackery, I tried to implemenet a trivial proxy model for User, containing just the 
# GenericRelation field. Doesn't work, though! Django complains about a field being defined on a proxy model.
#
# Looks like we have to enable the above hackery if we want an easy means of filtering users in a domain. Makes
# life easier, too, in that views will have access to this information.
#

User.add_to_class('domain_membership', 
                  generic.GenericRelation( Membership, content_type_field='member_type', object_id_field='member_id' ) )

##############################################################################################################
    

# Monkeypatch a function onto User to tell if user is administrator of selected domain
def _admin_p (self):
    dom = getattr(self, 'selected_domain', None)    
    if dom is not None:
        return self.has_row_perm(dom, Permissions.ADMINISTRATOR)
    else:
        return False
    
User.is_selected_dom_admin = _admin_p 