from django.db import models
from django.contrib.auth.models import Group, User
from django.utils.translation import ugettext_lazy as _
from reporters.models import Reporter, ReporterGroup


class Domain(models.Model):
    '''Domain is the highest level collection of people/stuff
       in the system.  Pretty much everything happens at the 
       domain-level, including permission to see data, reports,
       charts, etc.'''
    name = models.CharField(max_length=128, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    timezone = models.CharField(max_length=64,null=True)
        
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _("Domain Account")

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
    # The rationale for moving most of this information from ExtUser
    # is that most reporters shouldn't actually have django logins
           
    reporter = models.ForeignKey(Reporter, unique=True, related_name="profile")    
    # these fields are duplicates from ExtUser, and will replace
    # those when we sort out data migration
    chw_id = models.CharField(max_length=32, null=True, blank=True, help_text="integer id")
    chw_username = models.CharField(max_length=32, null=True, blank=True, help_text="chw_username in the app")
    
    # these fields are also duplicated in ExtUser, but ExtUsers need them too.
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
    
    def __unicode__(self):
        if self.chw_username:
            return "%s (%s)" % (self.chw_username, self.chw_id)
        else:
            return str(self.reporter)
    
    def __str__(self):
        return unicode(self).encode('utf-8')
        
class ExtUser(User):
    '''Extended users, which have some additional metadata associated with them'''
    
    # these have been moved to the ReporterProfile object and
    # should be removed when data migration gets sorted out  
    chw_id = models.CharField(max_length=32, null=True, blank=True, help_text="integer id")
    chw_username = models.CharField(max_length=32, null=True, blank=True, help_text="chw_username in the app")

    # this should be squashed by the reporter foreign key.  
    # unfortunately a lot of things currently like pointing at this
    # so it'll stick around temporarily
    primary_phone = models.CharField(max_length=30, null=True, blank=True, help_text="e.g., +251912555555")
    
    domain = models.ForeignKey(Domain)
    
    # also provide org-level granularity
    organization = models.ForeignKey("Organization", null=True, blank=True)
    
    # link to the rapidsms reporter 
    reporter = models.ForeignKey(Reporter, null=True, blank=True)
    
    @property
    def report_identity(self):         
        if self.chw_username == None:
            return self.__str__()
        else:
            return self.chw_username
    
    def __unicode__(self):
        if self.chw_username != None:
            return self.chw_username
        elif self.last_name != '':
            return self.last_name
        else:
            return self.username
    
    class Meta:
        verbose_name = _("Extended User")

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
    
    recipient_user =    models.ForeignKey(ExtUser, null=True, blank=True, 
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
        
