import hashlib
from django.db import models
from django.contrib.auth.models import Group, User
from django.utils.translation import ugettext_lazy as _

from domain.models import Domain 
from reporters.models import Reporter, ReporterGroup
from hq.processor import REGISTRATION_XMLNS, create_phone_user
import xformmanager.xmlrouter as xmlrouter


class OrganizationType(models.Model):
    name = models.CharField(max_length=64, unique=True)
    domain = models.ForeignKey(Domain)
    description = models.CharField(max_length=255, null=True, blank=True)    
    
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _("Organization Type")


class ReporterProfile(models.Model):
    '''The profile for a reporter object.  For attaching some of our
       own metadata-type information to RapidSMS reporters.  This is 
       loosely modeled on how django user profiles work.'''    
           
    reporter = models.ForeignKey(Reporter, unique=True, related_name="profile")    
    chw_id = models.CharField(max_length=32, null=True, blank=True, help_text="integer id")
    chw_username = models.CharField(max_length=32, null=True, blank=True, help_text="chw_username in the app")
    domain = models.ForeignKey(Domain)
    
    #dmyung - we will probably need to get rid of this unless there's a really compelling reason
    organization = models.ForeignKey("Organization", null=True, blank=True) 
    
    # todo: eventually make these non-null.
    guid = models.CharField(max_length=32, null=True, blank=True)
    approved = models.BooleanField(default=False)
    active = models.BooleanField(default=False)

    @property
    def report_identity(self):         
        if self.chw_username:
            return self.chw_username
        return str(self)
    
    @property
    def language(self):
        return self.reporter.language
    
    def send_message(self, router, msg):
        return self.reporter.send_message(router, msg)
    
    def __unicode__(self):
        if self.chw_username:
            return "%s (%s)" % (self.chw_username, self.chw_id)
        else:
            return str(self.reporter)
    
    def __str__(self):
        return unicode(self).encode('utf-8')

###### 02-11-2010 CZUE: Killing ExtUser but temporarily leaving around  ####### 
###### In commented form for reference                                  ####### 

#class ExtUser(User):
#    '''Extended users, which have some additional metadata associated with them'''
#    
#    # these have been moved to the ReporterProfile object and
#    # should be removed when data migration gets sorted out  
#    chw_id = models.CharField(max_length=32, null=True, blank=True, help_text="integer id")
#    chw_username = models.CharField(max_length=32, null=True, blank=True, help_text="chw_username in the app")
#
#    # this should be squashed by the reporter foreign key.  
#    # unfortunately a lot of things currently like pointing at this
#    # so it'll stick around temporarily
#    primary_phone = models.CharField(max_length=30, null=True, blank=True, help_text="e.g., +251912555555")
#    
#    domain = models.ForeignKey(Domain)
#    
#    # also provide org-level granularity
#    organization = models.ForeignKey("Organization", null=True, blank=True)
#    
#    # link to the rapidsms reporter 
#    reporter = models.ForeignKey(Reporter, null=True, blank=True)
#    
#    # the value of this field should *always* reflect the value of User.password in an ideal world
#    # for now, we allow null values, until such time as we want to reset everyone's password
#    unsalted_password = models.CharField(_('password'), max_length = 128, null=True, help_text = \
#                                         _("Use '[hexdigest]' or use the <a href=\"change_password/\">change password form</a>."))
#    
#    @property
#    def report_identity(self):         
#        if self.chw_username == None:
#            return self.__str__()
#        else:
#            return self.chw_username
#    
#    def __unicode__(self):
#        if self.first_name or self.last_name:
#            return "%s %s" % (self.first_name, self.last_name)
#        else:
#            return self.username
#    
#    class Meta:
#        verbose_name = _("Extended User")
#        
#    def set_unsalted_password(self, username, password):
#        # todo - integrate this with user.password
#        self.unsalted_password = hashlib.sha1( username+":"+password ).hexdigest()

class Organization(models.Model):
    # this should be renamed to "Group" if that term wasn't highly
    # overloaded already.  These really aren't organizations.
    '''An Organization.  Organizations are associated with domains.  They also 
       have parent/child hierarchies.  Currently an organization can have at 
       most 1 parent.  Top-level organizations don't have a parent.  
       Organizations also have members and supervisors.'''
    
    name = models.CharField(max_length=32, unique=True) #something's messed up with this (CZUE 6/9/2009: I didn't write this comment - what's messed up??) 
    domain = models.ForeignKey(Domain)
    description = models.CharField(max_length=255, null=True, blank=True)
    organization_type = models.ManyToManyField(OrganizationType)
    parent = models.ForeignKey("Organization", null=True, blank=True, related_name="children")
    
    # membership and supervision is modeled by rapidsms reporters
    # and groups
    members = models.ForeignKey(ReporterGroup, null=True, blank=True, related_name="members")
    supervisors = models.ForeignKey(ReporterGroup, null=True, blank=True, related_name="supervisors")
    
    class Meta:
        verbose_name = _("Organization")
    
    def __unicode__(self):
        return self.name
    
    def get_supervisors(self):
        if self.supervisors is None:
            return ReporterProfile.objects.none()
        reps = self.supervisors.reporters.all()
        return ReporterProfile.objects.filter(reporter__in=reps)
    
    def get_members(self):
        if self.members is None:
            return ReporterProfile.objects.none()
        members = self.members.reporters.all()
        return ReporterProfile.objects.filter(reporter__in=members)

REPORT_CLASS = (
    ('siteadmin', 'General Site Admin'),
    ('supervisor', 'Organizational Supervisor'),
    ('member', 'Organization Member'),
    ('domain', 'Custom Domain Report'),   
    ('other', 'Other Report Type'),   
)

REPORT_FREQUENCY = (
    ('weekly', 'Weekly'),
    ('daily', 'Daily'),
    ('monthly', 'Monthly'),
    ('quarterly', 'Quarterly'),
)

REPORT_DELIVERY = (
    ('sms', 'SMS'),
    ('email', 'Email'),    
)

class ReportSchedule(models.Model):
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=255)
    report_class =      models.CharField(_('Report Class'), max_length=32, choices=REPORT_CLASS)
    report_frequency =  models.CharField(_('Delivery Frequency'), max_length=32, choices=REPORT_FREQUENCY)
    report_delivery =   models.CharField(_('Delivery Transport/Method'), max_length=32, choices=REPORT_DELIVERY)
    
    recipient_user =    models.ForeignKey(User, null=True, blank=True, 
                                          help_text=_("If this is a General Site Admin report, enter the user you want to receive this report."))    
    organization =      models.ForeignKey(Organization, null=True, blank=True, 
                                          help_text=_("If this is an Organizational supervisor or member report, indicate the exact organization you want to report on."))
    
    report_function = models.CharField(max_length=255, null=True, blank=True, 
                                       help_text=_("The view or other python function  you want run for this report.  This is necessary only for General Site admin and Other report types."))
    active = models.BooleanField(default=True)
    
    @property
    def domain(self):
        '''Get the domain, trying first the organization, then the user.  If neither
           are set, will return nothing'''
        if self.organization:
            return self.organization.domain
        elif self.recipient_user:
            return self.recipient_user.domain
        return None
           
    def __unicode__(self):
        return unicode(self.name + " - " + self.report_frequency)
        
class BlacklistedUser(models.Model):
    '''Model for a blacklisted user.  Blacklisted users should be excluded from 
       most views of the data, including, but not limited to, charts, reports,
       submission logs(?), data/tabular views, etc.'''
    # this is a temporary solution until we get real reporters for everyone 
    # we care about.
    domains = models.ManyToManyField(Domain, related_name="blacklist")
    # could use reporters here, but this will keep things simple, which is 
    # desirable for a short-term solution
    username = models.CharField(max_length=64)
    # allow temporary enabling/disabling of blacklist at a global level.
    active = models.BooleanField(default=True)
    
    @classmethod
    def for_domain(cls, domain):
        """Get a flat blacklist of names for a domain, useful for doing 
           'in' queries or simple loops."""
        # NOTE: using this as a blacklist check implies a list lookup for each
        # user which could eventually get inefficient. We could make this a
        # hashset if desired to make this O(1)
        return domain.blacklist.filter(active=True)\
                        .values_list('username', flat=True)        

    def __unicode__(self):
        return "%s in %s" %\
                  (self.username, 
                   ",".join([domain.name for domain in self.domains.all()]))
                  
                  
# register our registration method, like a signal, in the models file
# to make sure this always gets bootstrapped.  
# TODO: it's unclear what app reg should belong to, for now stick it in
# the blanket "hq"
xmlrouter.register(REGISTRATION_XMLNS, create_phone_user)

