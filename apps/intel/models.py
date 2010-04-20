from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.db import connection
from datetime import *
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
    cursor = connection.cursor()
    cursor.execute(sql)
    return cursor.fetchall()

# turns a bunch of 2 value lists to dictionary. Used for group results    
def _result_to_dict(results):
    res = {}
    for row in results:
        res[row[0]] = row[1]

    return res
    

HI_RISK_INDICATORS = {
    'high_risk':
        {'short' : "Tot.",          'long' : "All High Risk",   'where' : "sampledata_hi_risk = 'yes'"},
    'hebp': 
        {'short' : "Hep B",         'long' : "Hepatitis B",             'where' : "sampledata_card_results_hepb_result = 'yes"},
    'previous_newborn_death': 
        {'short' : "Pr. NB Death",  'long' : "Previous Newborn Death",  'where' : "sampledata_previous_newborn_death = 'yes'"},
    'low_hemoglobin': 
        {'short' : "Lo Hmg",        'long' : "Low Hemoglobin",          'where' : "sampledata_card_results_hb_test = 'yes'"},
    'syphilis': 
        {'short' : "Syph.",         'long' : "Syphilis",                'where' : "sampledata_card_results_syphilis_result = 'yes'"},
    'rare_blood': 
        {'short' : "Blood",         'long' : "Rare Blood",              'where' : "sampledata_card_results_blood_group <> 'opositive' AND sampledata_card_results_blood_group <> 'apositive' AND sampledata_card_results_blood_group <> 'bpositive' AND sampledata_card_results_blood_group<>'abpositive' AND sampledata_card_results_blood_group IS NOT NULL"},
    'age_over_34': 
        {'short' : ">34",           'long' : "35 or Older",             'where' : 'sampledata_mother_age >= 34'},
    'previous_bleeding': 
        {'short' : "Bleed",         'long' : "Previous Bleeding",       'where' : "sampledata_previous_bleeding = 'yes'"},
    'over_5_pregs': 
        {'short' : ">5 pr",         'long' : "5+ Previous Pregnanices", 'where' : 'sampledata_previous_pregnancies >= 5'},
    'heart_problems': 
        {'short' : "Heart",         'long' : "Heart Problems",          'where' : "sampledata_heart_problems = 'yes'"},
    'previous_c_section':
        {'short' : "Pr. C",         'long' : "Previous C-Section",      'where' : "sampledata_previous_csection = 'yes'"},
    'time_since_last':
        {'short' : "Time",          'long' : "Last Checkup >5 Years Ago",'where' : "sampledata_over_5_years = 'yes'"},
    'age_under_19': 
        {'short' : "<19",           'long' : "18 or Younger",           'where' : "sampledata_mother_age <= 18"},
    'small_frame': 
        {'short' : "Small",         'long' : "Height 150cm or Less",    'where' : "sampledata_mother_height = 'under_150'"},
    'over_3_terminations': 
        {'short' : "3+ Term",       'long' : "Over 3 Past Terminations",'where' : 'sampledata_previous_terminations >= 3'},
    'hip_problems':
        {'short' : "Hip",           'long' : "Hip Problems",            'where' : "sampledata_hip_problems = 'yes'"},
    'diabetes':
        {'short' : "Diab.",         'long' : "Diabetes",                'where' : "sampledata_diabetes = 'yes'"}
}



def _date_format(startdate, enddate):
    return startdate.strftime("%Y-%m-%d"), (enddate + timedelta(days=1)).strftime("%Y-%m-%d")
    
    
def clinic_chart_sql(startdate, enddate, clinic_id):
    startdate, enddate = _date_format(startdate, enddate)
    return '''    
        SELECT DATE_FORMAT(timeend,'%%%%m/%%%%d/%%%%Y'), prof.username, count(*)
        FROM xformmanager_metadata meta,xformmanager_formdefmodel forms, hq_domain domains, intel_userclinic prof, intel_clinic
        WHERE forms.id = meta.formdefmodel_id AND intel_clinic.id = prof.clinic_id AND prof.username = meta.username 
            AND forms.domain_id = domains.id AND domains.name = 'Grameen' AND meta.timeend > '%s' AND meta.timeend < '%s' 
            AND clinic_id = %s
        GROUP BY DATE_FORMAT(timeend,'%%%%m/%%%%d/%%%%Y'), prof.username, clinic_id
        ORDER BY timeend ASC;
        ''' % (startdate, enddate, clinic_id)
        
    
def hq_chart_sql(startdate, enddate):
    startdate, enddate = _date_format(startdate, enddate)
    return '''    
        SELECT DATE_FORMAT(timeend,'%%%%m/%%%%d/%%%%Y'), intel_clinic.name as clinic, count(*)
        FROM xformmanager_metadata meta, xformmanager_formdefmodel forms, hq_domain domains, intel_userclinic prof, intel_clinic
        WHERE intel_clinic.id = prof.clinic_id AND prof.username = meta.username AND forms.id = meta.formdefmodel_id
            AND forms.domain_id = domains.id AND domains.name = 'Grameen' AND meta.timeend > '%s' AND meta.timeend < '%s'
        GROUP BY DATE_FORMAT(timeend,'%%%%m/%%%%d/%%%%Y'), clinic
        ORDER BY timeend ASC;
        ''' % (startdate, enddate)


def hq_risk_sql(clinic_id):
    return '''
        SELECT 
            COUNT(NULLIF(sampledata_hi_risk,'no')) AS high_risk,
            COUNT(NULLIF(sampledata_mother_height,'over_150')) AS small_frame,
            COUNT(NULLIF(sampledata_previous_csection,'no')) AS previous_c_section,
            COUNT(NULLIF(sampledata_previous_newborn_death,'no')) AS previous_newborn_death,
            COUNT(NULLIF(sampledata_previous_bleeding,'no')) AS previous_bleeding,
            COUNT(NULLIF(sampledata_heart_problems,'no')) AS heart_problems,
            COUNT(NULLIF(sampledata_diabetes,'no')) AS diabetes,
            COUNT(NULLIF(sampledata_hip_problems,'no')) AS hip_problems,
            COUNT(NULLIF(sampledata_card_results_syphilis_result,'negative')) AS syphilis,
            COUNT(NULLIF(sampledata_card_results_hepb_result,'negative')) AS hebp,
            COUNT(NULLIF(sampledata_over_5_years,'no')) AS time_since_last,
            COUNT(NULLIF(sampledata_card_results_hb_test,'normal')) AS low_hemoglobin,
            COUNT(IF(sampledata_mother_age <= 18, 1, NULL)) AS age_under_19,
            COUNT(IF(sampledata_mother_age >= 34, 1, NULL)) AS age_over_34,
            COUNT(IF(sampledata_previous_terminations >= 3, 1, NULL)) AS over_3_terminations,
            COUNT(IF(sampledata_previous_pregnancies >= 5, 1, NULL)) AS over_5_pregs, 
            COUNT(
                NULLIF(sampledata_card_results_blood_group, 'opositive') 
                OR NULLIF(sampledata_card_results_blood_group, 'apositive') 
                OR NULLIF(sampledata_card_results_blood_group, 'abpositive') 
                OR NULLIF(sampledata_card_results_blood_group, 'bpositive')) AS rare_blood
        FROM schema_intel_grameen_safe_motherhood_registration_v0_3, intel_userclinic 
        WHERE meta_username = intel_userclinic.username AND meta_username <> 'admin' AND intel_userclinic.clinic_id = %s;
        ''' % clinic_id
