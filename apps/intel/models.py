from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.db import connection

from domain.models import Membership

from intel.schema_models import *


# Adding roles and clinics to the user profile

class Role(models.Model):
    name = models.CharField(max_length=255)    

    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _("Role")


class Clinic(models.Model):
    name = models.CharField(max_length=255)

    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _("Clinic")


class UserProfile(models.Model):
    user    = models.ForeignKey(User, unique=True)
    clinic  = models.ForeignKey(Clinic)
    role    = models.ForeignKey(Role)


# schema specific methods - these use the inspectdb general schema_models.py which in turn dumps the models generated per the domain's xforms

REGISTRATION_TABLE = IntelGrameenMotherRegistration._meta.db_table
FOLLOWUP_TABLE     = IntelGrameenSafeMotherhoodFollowup._meta.db_table

def registrations():
    return IntelGrameenMotherRegistration.objects.filter(sampledata_meta_userid__gt=0)

def hi_risk():
    return IntelGrameenMotherRegistration.objects.filter(sampledata_meta_userid__gt=0, sampledata_hi_risk="yes")

def follow_up():
    return IntelGrameenSafeMotherhoodFollowup.objects.all()


# this is adapted from the various SqlReport stuff, which wasn't accurate (references xforms_ tables instead of actual data)
# and was a pain to use
# 
# TODO: see if Django GROUP BY equivalent is powerful enough to turn this to ORM code instead of SQL
def registrations_by_clinic():
    sql = ''' 
        select clinic_id, count(sampledata_case_id)
        from %s, intel_userprofile
        where sampledata_meta_userid > 0
        and sampledata_meta_userid = intel_userprofile.user_id
        group by clinic_id
    ''' % REGISTRATION_TABLE
    return _result_to_dict(_rawquery(sql))

def hi_risk_by_clinic():
    sql = ''' 
        select clinic_id, count(sampledata_case_id)
        from %s, intel_userprofile
        where sampledata_hi_risk = 'yes' and sampledata_meta_userid > 0
        and sampledata_meta_userid = intel_userprofile.user_id
        group by clinic_id
    ''' % REGISTRATION_TABLE
    return _result_to_dict(_rawquery(sql))

def followup_by_clinic():
    sql = ''' 
        select clinic_id, count(safe_pregnancy_case_id)
        from %s, intel_userprofile
        where safe_pregnancy_meta_userid > 0
        and safe_pregnancy_meta_userid = intel_userprofile.user_id
        group by clinic_id
    ''' % FOLLOWUP_TABLE
    return _result_to_dict(_rawquery(sql))

def _rawquery( sql):
    cursor = connection.cursor()
    cursor.execute(sql)
    return cursor.fetchall()

# turns a bunch of 2 value lists to dictionary. Used for group results    
def _result_to_dict(results):
    res = {}
    for row in results:
        res[row[0]] = row[1]

    return res


# # MemberRole.objects.filter(member = 4)
# # [<MemberRole: brian: chw>, <MemberRole: brian: doctor>]
# 
# class MemberRole(models.Model):
#     member = models.ForeignKey(Membership)
#     role = models.ForeignKey(Role)
# 
#     def __unicode__():
#         return "%s: %s" % (member.member_object, role)
#         
#     class Meta:
#         verbose_name = _("Member Role")
# 
#     
#     # helper method: get array of roles for a Member
#     # >>> MemberRole.per(4)
#     # [u'chw', u'doctor']
#     # useful for easily checking a user's role, eg:
#     # >>> if 'chw' in MemberRole.per(4): ...
#     
#     @staticmethod
#     def per(member):
#         roles = []
#         for r in MemberRole.objects.filter(member = member):
#             roles.append(r.role.name)
#         
#         return roles

