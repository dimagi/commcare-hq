from django.db import models
from django.contrib.auth.models import Group, User
from django.utils.translation import ugettext_lazy as _

from modelrelationship.models import *
from monitorregistry.models import *


class Domain(models.Model):
    name = models.CharField(max_length=128, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)
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


class ExtRole(models.Model):
    name = models.CharField(max_length=64, unique=True)
    domain = models.ForeignKey(Domain)
    description = models.CharField(max_length=255, null=True, blank=True)
    level = models.IntegerField()    
    
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _("Extended User Role")


class ExtUser(User):
    chw_id = models.CharField(max_length=32, null=True, blank=True, help_text="integer id")
    chw_username = models.CharField(max_length=32, null=True, blank=True, help_text="chw_username in the app")
    
    primary_phone = models.CharField(max_length=30, null=True, blank=True, help_text="e.g., +251912555555")
    domain = models.ForeignKey(Domain)
    identity = models.OneToOneField(MonitorIdentity, blank=True, null=True)
    
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
    '''An Organization.  Organizations are associated with domains.  They also 
       have parent/child hierarchies.  Currently an organization can have at 
       most 1 parent.  Top-level organizations don't have a parent.  
       Organizations also have members and supervisors.'''
       
    name = models.CharField(max_length=32, unique=True) #something's messed up with this (CZUE 6/9/2009: I didn't write this comment - what's messed up??) 
    domain = models.ForeignKey(Domain)
    description = models.CharField(max_length=255, null=True, blank=True)
    organization_type = models.ManyToManyField(OrganizationType)
    parent = models.ForeignKey("Organization", null=True, blank=True, related_name="children")
    members = models.ManyToManyField(ExtUser, null=True, blank=True, related_name="members")
    supervisors = models.ManyToManyField(ExtUser, null=True, blank=True, related_name="supervisors")
    
    class Meta:
        verbose_name = _("Organization")
    
    def __unicode__(self):
        return self.name

REPORT_CLASS = (
    ('siteadmin', 'General Site Admin'),
    ('supervisor', 'Organizational Supervisor'),
    ('member', 'Organization Member'),
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
    
    recipient_user =    models.ForeignKey(ExtUser, null=True, blank=True, help_text=_("If this is a General Site Admin report, enter the user you want to receive this report."))    
    organization =      models.ForeignKey(Organization, null=True, blank=True, help_text=_("If this is an Organizational supervisor or member report, indicate the exact organization you want to report on."))
    
    report_function = models.CharField(max_length=255, null=True, blank=True, help_text=_("The view or other python function  you want run for this report.  This is necessary only for General Site admin and Other report types."))
    active = models.BooleanField(default=True)
    
    def __unicode__(self):
        return unicode(self.name + " - " + self.report_frequency)
        