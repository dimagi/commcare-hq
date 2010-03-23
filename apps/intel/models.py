from django.db import models
from domain.models import Membership
# from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _


# ad hoc role system
# Role holds a list of roles w/ id
# Member role connects a domain member to a role
# A member may have more than 1 role

class Role(models.Model):
    name = models.CharField(max_length=255)
    
    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _("Role")

# MemberRole.objects.filter(member = 4)
# [<MemberRole: brian: chw>, <MemberRole: brian: doctor>]

class MemberRole(models.Model):
    member = models.ForeignKey(Membership)
    role = models.ForeignKey(Role)

    def __unicode__(self):
        return "%s: %s" % (self.member.member_object, self.role)
        
    class Meta:
        verbose_name = _("Member Role")

    
    # helper method: get array of roles for a Member
    # >>> MemberRole.per(4)
    # [u'chw', u'doctor']
    # useful for easily checking a user's role, eg:
    # >>> if 'chw' in MemberRole.per(4): ...
    
    @staticmethod
    def per(member):
        roles = []
        for r in MemberRole.objects.filter(member = member):
            roles.append(r.role.name)
        
        return roles



# class Clinic(models.Model):
#     name = models.CharField(max_length=255)
# 
#     def __unicode__(self):
#         return self.name
# 
#     class Meta:
#         verbose_name = _("Clinic")
# 
# 
# class UserClinic(models.Model):
#     user    = models.ForeignKey(User)
#     clinic  = models.ForeignKey(Clinic)