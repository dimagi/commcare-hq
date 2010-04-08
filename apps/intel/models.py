from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.db import connection

from domain.models import Membership

from intel.schema_models import *



# dropping roles - HQ is just another clinic.
class Clinic(models.Model):
    name = models.CharField(max_length=255)

    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _("Clinic")


# have to join on username, since user_ids are not consistent. So, UserProfile won't help here.
class UserClinic(models.Model):
    username = models.CharField(max_length=255)
    clinic = models.ForeignKey(Clinic, null=True, blank=True)

    def __unicode__(self):
        return "User: %s Clinic: %s" % (self.username, self.clinic.name)
    class Meta:
        verbose_name = _("User Clinic")


def get_role_for(user):
    # this is not ideal. UserProfile is supposed to take of this, and just provide User.get_profile().role
    # eg: role = UserProfile.objects.get(user=user.id).role
    # but it doesn't work. I suspect RapidSMS ignores AUTH_PROFILE_MODULE in local.ini
    try:
        role = UserProfile.objects.get(user=user.id).role
    except UserProfile.DoesNotExist:
        role = Role.objects.all()[0]

    return role


# schema specific methods - these use the inspectdb general schema_models.py which in turn dumps the models generated per the domain's xforms
REGISTRATION_TABLE = IntelGrameenMotherRegistration._meta.db_table
FOLLOWUP_TABLE     = IntelGrameenSafeMotherhoodFollowup._meta.db_table

def registrations():
    return IntelGrameenMotherRegistration.objects.exclude(meta_username='admin')

def hi_risk():
    return IntelGrameenMotherRegistration.objects.exclude(meta_username='admin').filter(sampledata_hi_risk="yes")

def follow_up():
    return IntelGrameenSafeMotherhoodFollowup.objects.all()


def registrations_by(group_by):
    sql = ''' 
        SELECT clinic_id, count(sampledata_case_id)
        FROM %s, intel_userclinic
        WHERE meta_username = intel_userclinic.username
        GROUP BY %s
    ''' % (REGISTRATION_TABLE, group_by)
    return _result_to_dict(_rawquery(sql))

def hi_risk_by(group_by):
    sql = ''' 
        SELECT clinic_id, count(sampledata_case_id)
        FROM %s, intel_userclinic
        WHERE sampledata_hi_risk = 'yes' and meta_username = intel_userclinic.username
        GROUP BY %s
    ''' % (REGISTRATION_TABLE, group_by)
    return _result_to_dict(_rawquery(sql))

def followup_by(group_by):
    sql = ''' 
        SELECT clinic_id, count(safe_pregnancy_case_id)
        FROM %s, intel_userclinic
        WHERE meta_username = intel_userclinic.username
        GROUP BY %s
    ''' % (FOLLOWUP_TABLE, group_by)
    return _result_to_dict(_rawquery(sql))



def _rawquery(sql):
    print sql
    cursor = connection.cursor()
    cursor.execute(sql)
    return cursor.fetchall()

# turns a bunch of 2 value lists to dictionary. Used for group results    
def _result_to_dict(results):
    res = {}
    for row in results:
        res[row[0]] = row[1]

    return res