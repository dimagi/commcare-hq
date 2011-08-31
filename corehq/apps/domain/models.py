from django.contrib.auth.models import User
from django.db import models

##############################################################################################################
#
# Originally had my own hacky global storage of content type, but it turns out that contenttype.models
# wisely caches content types! No hit to the db beyond the first call - no need for us to do our own 
# custom caching.
#
# See ContentType.get_for_model() code for details.

class Domain(models.Model):
    """Domain is the highest level collection of people/stuff
       in the system.  Pretty much everything happens at the 
       domain-level, including user membership, permission to 
       see data, reports, charts, etc."""

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
        if not hasattr(user,'get_profile'):
            # this had better be an anonymous user
            return Domain.objects.none()
        from corehq.apps.users.models import CouchUser
        couch_user = CouchUser.from_django_user(user)
        if couch_user:
            domain_names = couch_user.domain_names
            return Domain.objects.filter(name__in=domain_names)
        else:
            return Domain.objects.none()
    
    def add(self, model_instance, is_active=True):
        """
        Add something to this domain, through the generic relation.
        Returns the created membership object
        """
        # Add membership info to Couch
        couch_user = model_instance.get_profile().get_couch_user()
        couch_user.add_domain_membership(self.name)
        couch_user.save()
        
    def __unicode__(self):
        return self.name

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
    
##############################################################################################################
