from django.db import models
from monitorregistry.models import *
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import Group, User



#class OrganizationType(models.Model):
#    name = models.CharField(max_length=64, unique=True)
#    description = models.CharField(max_length=255, null=True, blank=True)
#    def __unicode__(self):
#        return self.name
#    pass
#
#class OrganizationRole(models.Model):
#    name = models.CharField(max_length=64, unique=True)
#    description = models.CharField(max_length=255, null=True, blank=True)
#    def __unicode__(self):
#        return self.name
#    pass


class OrganizationUnit(models.Model):
    name = models.CharField(max_length=32, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)
#    organization_type = models.ManyToManyField(OrganizationType)
#    roles = models.ManyToManyField(OrganizationRole)    
    member_of = models.ForeignKey('self',null=True,blank=True)  #recursive access baby!

    class Meta:
        verbose_name = _("Organizational Unit")
    
    def __unicode__(self):
        return self.name
    
class OrganizationGroup(Group):
    name = models.CharField(max_length=64)
    organization = models.ForeignKey(OrganizationUnit)
    description = models.CharField(max_length=255, null=True, blank=True)
    #monitor_group = models.ForeignKey(MonitorGroup)
    def __unicode__(self):
        return self.name