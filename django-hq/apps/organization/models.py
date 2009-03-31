from django.db import models
from monitorregistry.models import *
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import Group, User
from modelrelationship.models import *


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

#class OrgRelationshipType(EdgeType):     
#    class Meta:
#        verbose_name = _("Organization Relationship Type")
#
#class OrgRelationship(Edge):
#    class Meta:
#        verbose_name = _("Organization Relationship")

class ExtUser(User):    
    primary_phone = models.CharField(max_length=30, unique=True, null=True,blank=True, help_text="e.g., +251912555555")
    domain = models.ForeignKey(Domain)
    identity = models.OneToOneField(MonitorIdentity,blank=True,null=True)    
      
    def __unicode__(self):
        return self.username
    
    class Meta:
        verbose_name = _("Extended User")

class Organization(models.Model):
    name = models.CharField(max_length=32, unique=True) #something's messed up with this
    domain = models.ForeignKey(Domain)
    description = models.CharField(max_length=255, null=True, blank=True)
    organization_type = models.ManyToManyField(OrganizationType)    
    
    #member_of = models.ForeignKey('self',null=True,blank=True)  #recursive access baby! - this is negated with the edge modeling

    class Meta:
        verbose_name = _("Organization")
    
    def __unicode__(self):
        return self.name
